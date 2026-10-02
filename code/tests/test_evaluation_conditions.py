"""Offline condition/session orchestration against mocked Tutor responses."""

import copy
import csv
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation import runner
from evaluation.checks import run_checks, run_checks_for_run
from evaluation.corpus import (
    CorpusError,
    build_request_payload,
    case_profile_eligible,
    configuration_sha256,
    load_cases,
    load_profiles,
    sha256_file,
    sha256_json,
    validate_public_configuration,
)
from evaluation.models import Experiment, InteractionTurn, MAX_EVALUATION_HINT_LEVEL
from evaluation.report import (
    RFC_REVIEW_COLUMNS,
    build_report,
    compare_runs,
    export_review_packet,
    import_review_ratings,
)


DATA_DIR = runner.EVAL_DIR / "data"
PROFILES_PATH = DATA_DIR / "context_profiles.json"
CASE = load_cases(DATA_DIR / "example_cases.jsonl")[0]
PROFILES = load_profiles(PROFILES_PATH).by_id()
POLICY = json.loads(runner.POLICY_PATH.read_text(encoding="utf-8"))
SCRIPT = [
    {"message": "Was soll ich zuerst pruefen?", "elapsed_seconds": 0},
    {"message": "Ich verstehe nicht", "elapsed_seconds": 180, "confusion_signal": True},
]


def read_records(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_records(path: Path, values: list) -> None:
    path.write_text("".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")


def experiment(**changes) -> Experiment:
    return Experiment.model_validate({
        "schema_version": "1.0", "experiment_id": "conditions-v1",
        "protocol_version": "eval-protocol-1", "corpus_file": "cases.jsonl",
        "profiles": ["base"], "hint_levels": [1], "allow_unverified_cases": True,
        "models": ["generator-test"], **changes,
    })


def public_config(**rules) -> dict:
    configuration = {
        "schema_version": "tutor-config-1", "hint_policy": copy.deepcopy(POLICY),
        "start": {"mode": "individual", "level": 1, "min_level": 0, "max_level": 4},
        "generation": {"model": "generator-test", "temperature": 0.2, "max_tokens": 400},
        "adaptation": {"enabled": True, "after_seconds": 120, "step": 1, "max_level": 4},
        "tutor_rules": {
            "rules_id": "conditions-test", "policy_mode": "tutor", "diagnosis_mode": "provided",
            "enforce_word_limit": True, "hide_hint_level": True, **rules,
        },
        "context_defaults": PROFILES["base"].flags(),
        "stage0_context_options": PROFILES["base"].flags(),
    }
    return {"configuration": configuration, "config_sha256": configuration_sha256(configuration)}


def make_run(tmp_path: Path, name: str = "run-1", *, config=None, cases=None, **changes) -> Path:
    directory = tmp_path / name
    directory.mkdir()
    exp = experiment(**changes)
    exp_path = directory / "experiment.json"
    cases_path = directory / "cases.jsonl"
    exp_path.write_text(exp.model_dump_json(), encoding="utf-8")
    write_records(cases_path, [case.model_dump(mode="json") for case in cases or [CASE]])
    run_dir = directory / "run"
    runner.create_run(run_dir, exp_path, cases_path, PROFILES_PATH, "http://tutor.test", expected_config=config)
    return run_dir


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = []
        self.epoch = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)

    def clock(self) -> float:
        return self.now

    def wall(self) -> str:
        return (self.epoch + timedelta(seconds=self.now)).isoformat()

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TutorTransport:
    def __init__(self, config=None, levels=None) -> None:
        self.config = config or public_config()
        self.levels = levels or [0, 0, 1]
        self.calls = []
        self.chat_id = str(uuid.UUID(int=1))
        self.stack = None
        self.turn = -1
        self.mismatch = False
        self.fail_turn = None
        self.health_hash = True

    def __call__(self, method, url, payload, timeout):
        self.calls.append((method, url, copy.deepcopy(payload)))
        if url.endswith("/health"):
            body = {"tasks_loaded": 2, "default_model": "generator-test"}
            if self.health_hash:
                body["config_sha256"] = self.config["config_sha256"]
            return 200, body, None, ""
        if url.endswith("/api/evaluation/config"):
            return 200, self.config, None, ""
        if url.endswith("/start"):
            self.stack = payload["stack"]
            self.turn = 0
        else:
            assert url.endswith("/" + self.chat_id + "/message")
            assert "stack" not in payload and "student_answer" not in payload
            self.turn += 1
        if self.turn == self.fail_turn:
            return 500, {"detail": "sensitive upstream body"}, None, ""
        level = self.levels[min(self.turn, len(self.levels) - 1)]
        if payload.get("hint_level") is not None:
            level = payload["hint_level"]
        configuration = self.config["configuration"]
        options = dict(payload.get("context_options", configuration["context_defaults"]))
        if configuration["tutor_rules"]["diagnosis_mode"] in {"model", "none"}:
            options["include_diagnosis_code"] = options["include_prt_feedback"] = False
        if level == 0:
            options = {key: enabled and configuration["stage0_context_options"][key] for key, enabled in options.items()}
        content = []
        for field in ("question_text", "student_answer", "diagnosis_code", "prt_feedback"):
            if options["include_" + field] and self.stack.get(field):
                content.append("<" + field + ">\n" + self.stack[field] + "\n</" + field + ">")
        if payload.get("message"):
            content.append("<current_message>\n" + payload["message"] + "\n</current_message>")
        body = {
            "chat_id": self.chat_id, "question_id": self.stack["question_id"],
            "hint_level": level, "baseline_hint_level": self.levels[0], "model": "generator-test",
            "hint": "Welche Regel passt zur Struktur?", "context_options": options,
            "prompt_messages": [{"role": "system", "content": "policy"}, {"role": "user", "content": "\n".join(content)}],
            "start_prompt_messages": [{"role": "system", "content": "individual selection"}],
            "start_decision": {"mode": "individual", "selected_level": self.levels[0]},
            "adaptation": {"elapsed_seconds": payload.get("simulation_elapsed_seconds", 0)},
            "hint_policy": configuration["hint_policy"][str(level)],
            "configuration": configuration, "config_sha256": self.config["config_sha256"],
            "policy_mode": configuration["tutor_rules"]["policy_mode"],
            "stage": "diagnostic" if level == 0 else "hint",
            "diagnosis_hypothesis": None, "llm_operations": 2 if self.turn == 0 else 1,
            "not_public": "discard me",
        }
        if self.mismatch:
            body["config_sha256"] = "f" * 64
        return 200, body, None, ""


def execute(run_dir: Path, transport, clock=None, **options) -> dict:
    clock = clock or Clock()
    return runner.Runner(run_dir, transport=transport, sleep=clock.sleep, clock=clock.clock, wall_clock=clock.wall).run(
        execute_live=True, **options,
    )


@pytest.mark.parametrize("level", [0, 4, 5, MAX_EVALUATION_HINT_LEVEL])
def test_direct_levels_include_diagnostic_and_explicit_bounded_extensions(level):
    assert experiment(hint_levels=[level]).hint_levels == [level]


@pytest.mark.parametrize("levels", [[-1], [33], [], [True], ["0"]])
def test_invalid_evaluation_level_bounds(levels):
    with pytest.raises(ValidationError):
        experiment(hint_levels=levels)


@pytest.mark.parametrize("changes", [
    {"message": " "}, {"message": "x" * 2001}, {"elapsed_seconds": -1},
    {"elapsed_seconds": float("inf")}, {"elapsed_seconds": float("nan")},
    {"confusion_signal": "true"}, {"hint_level": 33}, {"updated_answer": "x"},
])
def test_script_turn_validation(changes):
    with pytest.raises(ValidationError):
        InteractionTurn.model_validate({"message": "What next?", **changes})


def test_experiment_defaults_and_server_start_placeholder():
    exp = experiment()
    assert exp.condition_id == "default" and exp.level_mode == "direct"
    assert exp.request_budget_units_per_hour == 80
    assert exp.allow_task_derived_cases is False and exp.interaction_script == []
    assert exp.expected_config_sha256 is None and exp.use_server_context is False
    with pytest.raises(ValidationError, match="hint_levels"):
        experiment(level_mode="server_start", hint_levels=[0, 1])
    with pytest.raises(ValidationError):
        experiment(expected_config_sha256="not-a-hash")
    with pytest.raises(ValidationError):
        experiment(policy_mode="general")


def test_configured_payload_keeps_explicit_data_pool_without_reference_metadata():
    payload = build_request_payload(CASE, PROFILES["steps"], None, "generator-test", use_server_context=True)
    assert "context_options" not in payload and payload["hint_level"] is None
    assert payload["stack"]["student_answer"] == CASE.tutor_context.student_answer
    assert payload["stack"]["final_answer"] == CASE.evaluation_only.reference.final_answer
    assert payload["stack"]["diagnosis_source"] == "synthetic"
    assert "evaluation_only" not in payload and "verification" not in payload["stack"]
    assert "expected_diagnosis" not in payload["stack"]


def test_every_eligible_shipped_payload_validates_against_api_stack_schema():
    from app.schemas import StackContext
    from evaluation.task_cases import cases_from_tasks

    cases = load_cases(DATA_DIR / "example_cases.jsonl") + cases_from_tasks(runner.CODE_DIR / "tasks")
    for case in cases:
        for profile in PROFILES.values():
            if case_profile_eligible(case, profile, True, True) is not None:
                continue
            for use_server_context in (False, True):
                payload = build_request_payload(case, profile, 1, None, use_server_context=use_server_context)
                stack = StackContext.model_validate(payload["stack"])
                assert stack.diagnosis_source in {None, "synthetic"}
        assert case.evaluation_only.provenance.response_origin == "synthetic_fixture"
        assert case.evaluation_only.verification.mathematics_status == "pending"


@pytest.mark.parametrize("origin,explicit,expected", [
    ("synthetic_fixture", None, "synthetic"),
    ("synthetic_fixture", "synthetic_fixture", "synthetic"),
    ("provided", None, "unknown"),
    ("prt", None, "unknown"),
    ("stack_prt", None, "unknown"),
    ("moodle_export", None, "unknown"),
    ("moodle_export", "provided", "provided"),
    ("moodle_export", "prt", "prt"),
    ("moodle_export", "stack", "stack"),
    ("moodle_export", "stack_prt", "stack_prt"),
])
def test_payload_source_uses_api_vocabulary_without_inferred_prt_authority(origin, explicit, expected):
    from app.schemas import StackContext

    case = CASE.model_copy(deep=True)
    case.evaluation_only.provenance.response_origin = origin
    case.tutor_context.diagnosis_source = explicit
    before = case.model_dump()
    payload = build_request_payload(case, PROFILES["diagnosis_feedback"], 1, None)
    assert payload["stack"]["diagnosis_source"] == expected
    StackContext.model_validate(payload["stack"])
    assert case.model_dump() == before
    assert build_request_payload(case, PROFILES["base"], 1, None)["stack"]["diagnosis_source"] is None


def test_task_derived_opt_in_never_fabricates_verification():
    case = CASE.model_copy(deep=True)
    case.tags.append("task_derived")
    assert case_profile_eligible(case, PROFILES["base"], True, False) is not None
    assert case_profile_eligible(case, PROFILES["base"], True, True) is None
    assert "nicht verifiziert" in case_profile_eligible(case, PROFILES["base"], False, True)
    assert case.evaluation_only.verification.mathematics_status == "pending"
    assert case.evaluation_only.verification.diagnosis_status == "pending"
    assert runner.build_plan(experiment(), [case], PROFILES_PATH)[0] == []
    assert len(runner.build_plan(experiment(allow_task_derived_cases=True), [case], PROFILES_PATH)[0]) == 1


def test_sessions_are_deterministic_and_only_sessions_are_shuffled(tmp_path):
    cases = load_cases(DATA_DIR / "example_cases.jsonl")[:2]
    exp = experiment(level_mode="server_start", hint_levels=[0], repetitions=2, interaction_script=SCRIPT)
    original = exp.model_dump()
    jobs, exclusions = runner.build_plan(exp, cases, PROFILES_PATH)
    assert (jobs, exclusions) == runner.build_plan(exp, cases, PROFILES_PATH)
    assert exp.model_dump() == original
    assert len(jobs) == 12 and exclusions == []
    assert len({job["session_id"] for job in jobs}) == 4
    for offset in range(0, len(jobs), 3):
        start, first, second = jobs[offset:offset + 3]
        assert [job["turn_index"] for job in (start, first, second)] == [0, 1, 2]
        assert len({job["session_id"] for job in (start, first, second)}) == 1
        assert start["request_payload"]["hint_level"] is None
        assert start["request_payload"]["chat_id"] is None
        assert first["depends_on_job_id"] == start["job_id"]
        assert second["depends_on_job_id"] == first["job_id"]
        assert second["parent_job_id"] == start["job_id"]
        assert first["request_path"] == "/api/tutor/{chat_id}/message"
        assert second["request_payload"]["simulation_elapsed_seconds"] == 180
        assert second["request_payload"]["confusion_signal"] is True
        assert "hint_level" not in second["request_payload"]
        assert first["stack_context"]["student_answer"] == start["request_payload"]["stack"]["student_answer"]


def test_control_repetition_numbers_and_no_duplicate_cells():
    exp = experiment(control_jobs=[{
        "case_id": CASE.case_id, "profile_id": "diagnosis", "hint_level": 0, "repetitions": 3,
    }])
    jobs, _ = runner.build_plan(exp, [CASE], PROFILES_PATH)
    controls = [job for job in jobs if job["block"] == "control"]
    assert [job["repetition"] for job in controls] == [1, 2, 3]
    assert len({job["session_id"] for job in jobs}) == len(jobs)
    exp.control_jobs.append(exp.control_jobs[0])
    with pytest.raises(CorpusError, match="verdoppelt"):
        runner.build_plan(exp, [CASE], PROFILES_PATH)


def test_history_requires_a_script(tmp_path):
    profiles_path = tmp_path / "profiles.json"
    profile = PROFILES["base"].model_copy(update={"include_chat_history": True})
    write_json(profiles_path, {"schema_version": "1.0", "profiles": [profile.model_dump()]})
    with pytest.raises(CorpusError, match="interaction_script"):
        runner.build_plan(experiment(), [CASE], profiles_path)
    jobs, _ = runner.build_plan(experiment(interaction_script=SCRIPT), [CASE], profiles_path)
    assert all(job["request_payload"]["context_options"]["include_chat_history"] for job in jobs)


def test_manifest_pins_plan_and_public_condition(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, condition_id="individual", level_mode="server_start", hint_levels=[0], interaction_script=SCRIPT)
    manifest = runner.load_manifest(run_dir)
    assert manifest["expected_config_sha256"] == config["config_sha256"]
    assert manifest["expected_configuration"] == config
    assert manifest["counts"]["sessions"] == 1 and manifest["counts"]["jobs"] == 3
    assert manifest["plan_sha256"] == sha256_file(run_dir / "plan.jsonl")
    assert manifest["condition_sha256"]
    with pytest.raises(runner.RunnerError, match="not empty"):
        runner.create_run(run_dir, Path(manifest["paths"]["experiment"]), Path(manifest["paths"]["corpus"]), PROFILES_PATH, "http://tutor.test")
    jobs = read_records(run_dir / "plan.jsonl")
    jobs[1]["request_payload"]["message"] = "changed"
    write_records(run_dir / "plan.jsonl", jobs)
    with pytest.raises(runner.RunnerError, match="plan changed"):
        runner.verify_manifest(run_dir, manifest)
    manifest.pop("plan_sha256")
    manifest["hashes"].pop("plan_file")
    runner.verify_manifest(run_dir, manifest)  # Existing artifacts had no plan hash.


def test_script_dispatch_records_observed_stages_policy_and_simulated_clock(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, condition_id="adaptive", level_mode="server_start", hint_levels=[0], interaction_script=SCRIPT)
    clock = Clock()
    transport = TutorTransport(config)
    stats = execute(run_dir, transport, clock)
    assert stats["success"] == stats["dispatched"] == 3
    assert clock.sleeps == []  # Simulated 180 seconds did not sleep.
    records = read_records(run_dir / "generations.jsonl")
    assert [record["effective_hint_level"] for record in records] == [0, 0, 1]
    assert [record["returned"]["stage"] for record in records] == ["diagnostic", "diagnostic", "hint"]
    assert all(record["condition_id"] == "adaptive" for record in records)
    assert all(record["budget_cost"] == record["llm_budget_units"] == 4 for record in records)
    assert records[-1]["request_path"].endswith("/" + transport.chat_id + "/message")
    assert records[-1]["returned"]["adaptation"]["elapsed_seconds"] == 180
    assert records[0]["returned"]["llm_operations"] == 2
    assert records[0]["returned"]["start_prompt_messages"]
    assert all("not_public" not in record["returned"] for record in records)
    assert all(record["hint_policy_sha256"] == sha256_json(record["returned"]["hint_policy"]) for record in records)
    assert run_checks_for_run(run_dir)["failed"] == 0
    assert runner.load_manifest(run_dir)["runtime"]["configuration"] == config["configuration"]


@pytest.mark.parametrize("health_hash", [None, "e" * 64])
def test_expected_config_missing_or_different_health_fails_before_dispatch(tmp_path, health_hash):
    config = public_config()
    run_dir = make_run(tmp_path, expected_config_sha256=config["config_sha256"])
    calls = []

    def transport(method, url, payload, timeout):
        calls.append(method)
        return 200, {"config_sha256": health_hash}, None, ""

    with pytest.raises(runner.RunnerError, match="pinned"):
        execute(run_dir, transport)
    assert calls == ["GET"] and not (run_dir / "generations.jsonl").exists()


def test_config_mismatch_is_not_success_and_blocks_dependent_turns(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    transport = TutorTransport(config)
    transport.mismatch = True
    stats = execute(run_dir, transport)
    assert stats["success"] == 0 and stats["configuration_mismatch"] == 1
    assert stats["skipped_dependency"] == 2 and stats["dispatched"] == 1
    record = read_records(run_dir / "generations.jsonl")[0]
    assert record["outcome"] == "configuration_mismatch" and record["returned"]
    with pytest.raises(runner.RunnerError, match="configuration-mismatched"):
        execute(run_dir, transport, resume=True, retry_failed=True)


def test_configuration_change_stops_remaining_independent_requests(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, cases=load_cases(DATA_DIR / "example_cases.jsonl")[:2])
    transport = TutorTransport(config)
    transport.mismatch = True
    stats = execute(run_dir, transport)
    assert stats["configuration_mismatch"] == 1 and stats["dispatched"] == 1
    assert stats["skipped_configuration"] == 1


def test_resume_preflight_even_when_all_jobs_succeeded(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config)
    transport = TutorTransport(config)
    execute(run_dir, transport)
    transport.calls.clear()
    assert execute(run_dir, transport, resume=True)["dispatched"] == 0
    assert [url.rsplit("/", 1)[-1] for _method, url, _payload in transport.calls] == ["health", "config"]
    changed = public_config(rules_id="changed-server")
    with pytest.raises(runner.RunnerError, match="pinned"):
        execute(run_dir, TutorTransport(changed), resume=True)


def test_resume_follows_saved_chat_without_replaying_start(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    clock = Clock()
    first = TutorTransport(config)

    def interrupted(method, url, payload, timeout):
        if method == "POST" and not url.endswith("/start"):
            raise KeyboardInterrupt
        return first(method, url, payload, timeout)

    with pytest.raises(KeyboardInterrupt):
        execute(run_dir, interrupted, clock)
    records = read_records(run_dir / "generations.jsonl")
    assert len(records) == 1 and records[0]["outcome"] == "success"
    second = TutorTransport(config)
    stats = execute(run_dir, second, clock, resume=True, retry_failed=True)
    assert stats["in_flight_repaired"] == 1 and stats["dispatched"] == 0
    assert stats["skipped_completed"] == 1 and stats["skipped_dependency"] == 1
    assert all(method == "GET" for method, _url, _payload in second.calls)


def test_resume_uses_successful_predecessor_chat_for_pending_turns(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    transport = TutorTransport(config)

    def fail_before_next_attempt(cost):
        if read_records(run_dir / "generations.jsonl"):
            raise KeyboardInterrupt
        return 0

    clock = Clock()
    interrupted = runner.Runner(run_dir, transport=transport, sleep=clock.sleep, clock=clock.clock, wall_clock=clock.wall)
    interrupted.wait_for_budget = fail_before_next_attempt
    with pytest.raises(KeyboardInterrupt):
        interrupted.run(execute_live=True)
    transport.calls.clear()
    stats = execute(run_dir, transport, clock, resume=True)
    assert stats["success"] == stats["dispatched"] == 2
    assert stats["skipped_completed"] == 1
    assert all(not url.endswith("/start") for method, url, _payload in transport.calls if method == "POST")
    assert [record["turn_index"] for record in read_records(run_dir / "generations.jsonl")] == [0, 1, 2]


def test_explicit_script_target_is_sent_without_automatic_timer_target(tmp_path):
    config = public_config()
    script = [{"message": "Please continue", "elapsed_seconds": 180, "hint_level": 3}]
    run_dir = make_run(tmp_path, config=config, interaction_script=script)
    transport = TutorTransport(config)
    execute(run_dir, transport)
    record = read_records(run_dir / "generations.jsonl")[-1]
    assert record["request_payload"]["hint_level"] == record["effective_hint_level"] == 3
    assert record["request_payload"]["simulation_elapsed_seconds"] == 180


def test_journal_is_durable_before_dispatch_and_exception_is_ambiguous(tmp_path):
    run_dir = make_run(tmp_path)
    base = TutorTransport()

    def transport(method, url, payload, timeout):
        if method == "POST":
            starts = [event for event in read_records(run_dir / "events.jsonl") if event["event"] == "attempt_started"]
            assert len(starts) == 1 and starts[0]["request_payload"] == payload
            raise RuntimeError("private upstream secret")
        return base(method, url, payload, timeout)

    stats = execute(run_dir, transport)
    assert stats["transport_ambiguous"] == 1
    assert "private upstream secret" not in (run_dir / "generations.jsonl").read_text(encoding="utf-8")


def test_failed_followup_is_not_reposted_without_idempotency(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    transport = TutorTransport(config)
    transport.fail_turn = 1
    first = execute(run_dir, transport)
    assert first["server_error"] == 1 and first["skipped_dependency"] == 1
    records = read_records(run_dir / "generations.jsonl")
    assert records[-1]["session_retry_safe"] is False
    transport.calls.clear()
    second = execute(run_dir, transport, resume=True, retry_failed=True)
    assert second["dispatched"] == 0
    assert all(method == "GET" for method, _url, _payload in transport.calls)


def test_weighted_budget_includes_judge_and_survives_kernel_restart(tmp_path):
    run_dir = make_run(tmp_path, request_budget_units_per_hour=6)
    clock = Clock()
    write_records(run_dir / "events.jsonl", [{
        "event": "attempt_started", "attempt_id": "generator-old", "ts_utc": clock.wall(),
    }])
    judge_dir = run_dir / "reviews" / "judge" / "judge-1"
    judge_dir.mkdir(parents=True)
    write_records(judge_dir / "events.jsonl", [{
        "event": "attempt_started", "attempt_id": "judge-old", "budget_cost": 2, "ts_utc": clock.wall(),
    }])
    budget = runner.Runner(run_dir, sleep=clock.sleep, clock=clock.clock, wall_clock=clock.wall)
    assert budget.wait_for_budget(4) == 3600
    assert clock.sleeps == [3600]
    restarted_clock = Clock()
    restarted = runner.Runner(run_dir, sleep=restarted_clock.sleep, clock=restarted_clock.clock, wall_clock=restarted_clock.wall)
    assert restarted.wait_for_budget(4) == 3600
    assert restarted_clock.sleeps == [3600]


def test_weighted_budget_default_caps_before_old_generation_limit(tmp_path):
    run_dir = make_run(tmp_path, request_budget_units_per_hour=4)
    clock = Clock()
    transport = TutorTransport()
    execute(run_dir, transport, clock)
    write_records(run_dir / "events.jsonl", read_records(run_dir / "events.jsonl") + [{
        "event": "attempt_started", "attempt_id": "judge-2", "budget_cost": 2, "ts_utc": clock.wall(),
    }])
    budget = runner.Runner(run_dir, sleep=clock.sleep, clock=clock.clock, wall_clock=clock.wall)
    assert budget.wait_for_budget(4) == 3600


def test_config_canonical_hash_matches_public_api_and_refuses_credentials():
    config = public_config()
    config["configuration"]["hint_policy"]["1"]["goal"] = "Pruefe die innere Funktion"
    config["config_sha256"] = configuration_sha256(config["configuration"])
    assert validate_public_configuration(config) == config
    config["configuration"]["evaluation_token"] = "do-not-save"
    config["config_sha256"] = configuration_sha256(config["configuration"])
    with pytest.raises(CorpusError, match="Credentials"):
        validate_public_configuration(config)


def test_transport_uses_local_token_but_never_records_it(tmp_path, monkeypatch):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    token = "test-only-evaluation-credential"
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", token)
    transport = TutorTransport(config)
    headers = []

    class Response:
        def __init__(self, body):
            self.status_code = 200
            self.body = body

        def json(self):
            return self.body

    def request(method, url, **kwargs):
        headers.append(kwargs["headers"])
        assert kwargs["verify"] is True and kwargs["allow_redirects"] is False
        _status, body, _error, _detail = transport(method, url, kwargs.get("json"), kwargs["timeout"])
        return Response(body)

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: request("GET", url, **kwargs))
    monkeypatch.setattr(requests, "post", lambda url, **kwargs: request("POST", url, **kwargs))
    clock = Clock()
    stats = runner.Runner(run_dir, sleep=clock.sleep, clock=clock.clock, wall_clock=clock.wall).run(execute_live=True)
    assert stats["success"] == 3
    assert all(value == {"X-Evaluation-Token": token} for value in headers)
    assert not any(token in path.read_text(encoding="utf-8") for path in run_dir.glob("*.json*"))


def test_returned_credential_echoes_are_redacted_recursively(monkeypatch):
    token = "private-local-evaluation-token"
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", token)
    returned = runner._extract_returned({
        "hint": "Echo " + token,
        "adaptation": {"secret": token, "nested": [token]},
        "start_decision": {"authorization": token, "mode": "fixed"},
        "configuration": {"evaluation_token": token},
    })
    assert token not in json.dumps(returned)
    assert "secret" not in returned["adaptation"]
    assert "authorization" not in returned["start_decision"]


def test_checks_use_effective_config_caps_and_actual_active_policy(tmp_path):
    config = public_config(diagnosis_mode="model", enforce_word_limit=False, hide_hint_level=False)
    config["configuration"]["context_defaults"] = PROFILES["diagnosis_feedback"].flags()
    config["config_sha256"] = configuration_sha256(config["configuration"])
    run_dir = make_run(tmp_path, config=config, profiles=["diagnosis_feedback"], hint_levels=[0])
    transport = TutorTransport(config)
    execute(run_dir, transport)
    record = read_records(run_dir / "generations.jsonl")[0]
    record["returned"]["hint"] = "Hilfestufe 0 " + "Wort " * 100
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["diagnosis_feedback"], POLICY)}
    assert checks["context_options_match"]["status"] == "pass"
    assert checks["prompt_required_content"]["status"] == "pass"
    assert "diagnosis_code" not in checks["prompt_required_content"]["evidence"]["checked_parts"]
    assert checks["word_count"]["status"] == "not_applicable"
    assert checks["hint_level_mention"]["status"] == "not_applicable"
    record["returned"]["hint_policy"]["max_words"] = 1
    record["returned"]["configuration"]["tutor_rules"]["enforce_word_limit"] = True
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["diagnosis_feedback"], POLICY)}
    assert checks["word_count"]["status"] == "fail"
    assert checks["word_count"]["evidence"]["max_words"] == 1
    assert checks["configuration_identity"]["status"] == "fail"


def test_general_mode_separates_detected_full_answer_from_prohibition(tmp_path):
    config = public_config(policy_mode="general")
    run_dir = make_run(tmp_path, config=config)
    execute(run_dir, TutorTransport(config))
    record = read_records(run_dir / "generations.jsonl")[0]
    record["returned"]["hint"] = CASE.evaluation_only.reference.final_answer
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["base"], POLICY)}
    disclosure = checks["final_answer_disclosure"]
    assert disclosure["status"] == "not_applicable"
    assert disclosure["evidence"]["present"] is True
    assert disclosure["evidence"]["prohibited_disclosure"] is None
    assert checks["word_count"]["status"] == "not_applicable"
    write_records(run_dir / "generations.jsonl", [record])
    write_records(run_dir / "checks.jsonl", list(checks.values()))
    build_report(run_dir)
    with (run_dir / "derived" / "summary.csv").open(encoding="utf-8") as handle:
        summary = next(csv.DictReader(handle))
    assert summary["complete_solution_present"] == "1"
    assert summary["prohibited_disclosure"] == "0"


def test_configured_context_and_missing_real_prompt_remain_observable(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, use_server_context=True)
    execute(run_dir, TutorTransport(config))
    record = read_records(run_dir / "generations.jsonl")[0]
    assert "context_options" not in record["request_payload"]
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["base"], POLICY)}
    assert checks["context_options_match"]["status"] == "pass"
    record["returned"]["prompt_messages"] = None
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["base"], POLICY)}
    assert checks["prompt_required_content"]["status"] == "inconclusive"
    assert checks["prompt_solution_guard"]["status"] == "inconclusive"


def test_followup_current_message_required_even_when_history_disabled(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, interaction_script=SCRIPT)
    execute(run_dir, TutorTransport(config))
    record = read_records(run_dir / "generations.jsonl")[-1]
    record["returned"]["prompt_messages"][-1]["content"] = CASE.tutor_context.question_text + "\n" + CASE.tutor_context.student_answer
    record["returned"]["prompt_messages"].insert(1, {"role": "user", "content": SCRIPT[-1]["message"]})
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["base"], POLICY)}
    assert checks["prompt_required_content"]["status"] == "fail"
    assert "current_message" in checks["prompt_required_content"]["evidence"]["missing"]


def test_wrong_explicit_followup_level_and_missing_effective_flags_do_not_pass(tmp_path):
    config = public_config()
    script = [{"message": "Next please", "hint_level": 3}]
    run_dir = make_run(tmp_path, config=config, interaction_script=script)
    execute(run_dir, TutorTransport(config))
    record = read_records(run_dir / "generations.jsonl")[-1]
    record["returned"]["hint_level"] = 2
    record["returned"]["stage"] = "hint"
    record["returned"]["context_options"] = None
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["base"], POLICY)}
    assert checks["response_identity"]["status"] == "fail"
    assert checks["context_options_match"]["status"] == "fail"
    assert checks["prompt_required_content"]["status"] == "inconclusive"


def test_observed_policy_limits_steps_even_when_local_policy_allows_more(tmp_path):
    config = public_config()
    config["configuration"]["hint_policy"]["3"]["max_solution_steps"] = 1
    config["config_sha256"] = configuration_sha256(config["configuration"])
    run_dir = make_run(tmp_path, config=config, hint_levels=[3], profiles=["steps"])
    execute(run_dir, TutorTransport(config))
    record = read_records(run_dir / "generations.jsonl")[0]
    first, second = CASE.evaluation_only.reference.solution_steps[:2]
    record["returned"]["prompt_messages"][-1]["content"] += "\n" + first
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["steps"], POLICY)}
    assert checks["prompt_solution_guard"]["status"] == "pass"
    record["returned"]["prompt_messages"][-1]["content"] += "\n" + second
    checks = {check["check_id"]: check for check in run_checks(record, CASE, PROFILES["steps"], POLICY)}
    assert checks["prompt_solution_guard"]["status"] == "fail"
    assert "solution_step_limit" in checks["prompt_solution_guard"]["evidence"]["leaked"]


def rate_packet(run_dir: Path, score: int) -> list:
    export_review_packet(run_dir)
    path = run_dir / "reviews" / "review_packet.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    for row in rows:
        row.update(rater_id="human-test", hilfreichkeit_naechster_schritt=str(score))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RFC_REVIEW_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    assert import_review_ratings(run_dir, path)["imported"] == len(rows)
    return rows


def test_condition_reports_and_pairs_keep_adaptive_outcomes_separate(tmp_path):
    config = public_config()
    baseline = make_run(tmp_path, "baseline", config=config, condition_id="fixed", level_mode="server_start", hint_levels=[0], interaction_script=SCRIPT)
    candidate = make_run(tmp_path, "candidate", config=config, condition_id="adaptive", level_mode="server_start", hint_levels=[0], interaction_script=SCRIPT)
    execute(baseline, TutorTransport(config, levels=[0, 0, 1]))
    execute(candidate, TutorTransport(config, levels=[2, 2, 3]))
    rows = rate_packet(baseline, 3)
    rate_packet(candidate, 5)
    assert rows[-1]["studentische_antwort"] == CASE.tutor_context.student_answer
    assert rows[-1]["aktuelle_nachricht"] == SCRIPT[-1]["message"]
    assert rows[-1]["dialogschritt"] == "2"
    assert all("condition_id" not in row and "model" not in row and "profile_id" not in row for row in rows)
    report = build_report(candidate)
    assert report["summary_rows"] == 3
    with (candidate / "derived" / "summary.csv").open(encoding="utf-8") as handle:
        summary = list(csv.DictReader(handle))
    assert {row["condition_id"] for row in summary} == {"adaptive"}
    assert {row["turn_index"] for row in summary} == {"0", "1", "2"}
    comparisons = compare_runs([baseline, candidate])
    assert comparisons["coverage"]["paired_human_ratings"] == 3
    assert comparisons["coverage"]["unmatched_cells"] == 0
    assert all(row["delta"] == 2 for row in comparisons["paired_rows"])
    assert comparisons["paired_rows"][0]["reference_effective_hint_level"] == 0
    assert comparisons["paired_rows"][0]["effective_hint_level"] == 2


def test_different_scripts_never_pair_and_missing_ratings_stay_missing(tmp_path):
    config = public_config()
    left = make_run(tmp_path, "left", config=config, condition_id="left", interaction_script=SCRIPT)
    right = make_run(tmp_path, "right", config=config, condition_id="right", interaction_script=[{"message": "Other question"}])
    execute(left, TutorTransport(config))
    execute(right, TutorTransport(config))
    assert compare_runs([left, right])["coverage"]["paired_responses"] == 0
    right_same = make_run(tmp_path, "right-same", config=config, condition_id="right-same", interaction_script=SCRIPT)
    execute(right_same, TutorTransport(config))
    pairs = compare_runs([left, right_same])
    assert pairs["coverage"]["paired_responses"] == 3
    assert pairs["coverage"]["pairs_missing_human_ratings"] == 3
    assert all(row["delta"] is None for row in pairs["paired_rows"])


def test_same_case_id_with_changed_answer_does_not_pair(tmp_path):
    config = public_config()
    left = make_run(tmp_path, "left", config=config, condition_id="left")
    case = CASE.model_copy(deep=True)
    case.tutor_context.student_answer = "different controlled answer"
    right = make_run(tmp_path, "right", config=config, condition_id="right", cases=[case])
    execute(left, TutorTransport(config))
    execute(right, TutorTransport(config))
    pairs = compare_runs([left, right])
    assert pairs["coverage"]["paired_responses"] == 0
    assert pairs["exclusions"][0]["reason"] == "case_identity_missing_or_changed"


def test_comparison_retains_jobs_failed_or_blocked_in_both_conditions(tmp_path):
    config = public_config()
    left = make_run(tmp_path, "left", config=config, condition_id="left", interaction_script=SCRIPT)
    right = make_run(tmp_path, "right", config=config, condition_id="right", interaction_script=SCRIPT)
    for directory in (left, right):
        transport = TutorTransport(config)
        transport.fail_turn = 0
        assert execute(directory, transport)["server_error"] == 1
    comparison = compare_runs([left, right])
    assert comparison["coverage"]["paired_responses"] == 0
    assert comparison["coverage"]["expected_comparison_cells"] == 3
    assert comparison["coverage"]["unmatched_cells"] == 3
    assert all(not item["reference_available"] and not item["condition_available"] for item in comparison["exclusions"])


def test_profile_pairs_do_not_cross_conditions_or_turns(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, condition_id="fixed", profiles=["base", "diagnosis"])
    execute(run_dir, TutorTransport(config))
    rate_packet(run_dir, 4)
    assert build_report(run_dir)["paired_rows"] == 1
    records = read_records(run_dir / "generations.jsonl")
    diagnosis = next(record for record in records if record["profile_id"] == "diagnosis")
    diagnosis["condition_id"] = "different-condition"
    write_records(run_dir / "generations.jsonl", records)
    assert build_report(run_dir)["paired_rows"] == 0
    diagnosis["condition_id"] = "fixed"
    diagnosis["turn_index"] = 1
    write_records(run_dir / "generations.jsonl", records)
    assert build_report(run_dir)["paired_rows"] == 0


def test_judge_and_demo_ratings_never_enter_human_condition_metrics(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, condition_id="human-only")
    execute(run_dir, TutorTransport(config))
    rows = rate_packet(run_dir, 4)
    ratings_path = run_dir / "reviews" / "ratings.jsonl"
    human = read_records(ratings_path)[0]
    write_records(ratings_path, [human, {
        **human, "rater_id": "model-judge", "rating_source": "model_judge", "ratings": {"hilfreichkeit_naechster_schritt": 1},
    }])
    results = read_records(run_dir / "generations.jsonl")
    write_records(run_dir / "generations.jsonl", results + [{
        **results[0], "attempt_id": "demo-1", "execution_source": "offline_demo",
    }])
    report = build_report(run_dir)
    assert report["coverage"]["responses_total"] == 1
    assert report["coverage"]["ratings_total"] == 1
    assert report["coverage"]["responses_with_ratings"] == 1
    imported_path = run_dir / "model-rating.csv"
    with imported_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RFC_REVIEW_COLUMNS + ["rating_source"], delimiter=";")
        writer.writeheader()
        writer.writerow({**rows[0], "rating_source": "model_judge", "rater_id": "model-judge"})
    with pytest.raises(ValueError, match="human ratings"):
        import_review_ratings(run_dir, imported_path)


@pytest.fixture
def selector_evidence():
    """Distinct synthetic markers avoid overlap between permitted context fields."""
    case = CASE.model_copy(deep=True)
    case.tutor_context.question_text = "QUESTION_ONLY_MARKER"
    case.tutor_context.student_answer = "STUDENT_ONLY_MARKER"
    case.tutor_context.diagnosis_code = "DIAGNOSIS_ONLY_MARKER"
    case.tutor_context.prt_feedback = "FEEDBACK_ONLY_MARKER"
    case.tutor_context.score = 0.0
    case.tutor_context.learning_goals = ["GOAL_ONLY_MARKER"]
    case.tutor_context.math_rules = ["RULE_ONLY_MARKER"]
    case.evaluation_only.reference.solution_steps = ["STEP_ONLY_MARKER"]
    case.evaluation_only.reference.final_answer = "FINAL_ONLY_MARKER"
    case.evaluation_only.reference.equivalent_forms = ["EQUIVALENT_ONLY_MARKER"]
    profile = PROFILES["knowledge"].model_copy(update={"include_score": True})
    payload = build_request_payload(case, profile, None, "generator-test")
    config = public_config()
    config["configuration"]["context_defaults"] = profile.flags()
    config["configuration"]["stage0_context_options"] = profile.flags()
    config["config_sha256"] = configuration_sha256(config["configuration"])
    content = "\n".join([
        "<question_text>\nQUESTION_ONLY_MARKER\n</question_text>",
        "<student_answer>\nSTUDENT_ONLY_MARKER\n</student_answer>",
        "DIAGNOSIS_ONLY_MARKER", "FEEDBACK_ONLY_MARKER", "STACK-SCORE:\n0.0",
        "GOAL_ONLY_MARKER", "RULE_ONLY_MARKER",
    ])
    generation = {
        "attempt_id": "selector-attempt", "job_id": "selector-job", "outcome": "success",
        "condition_id": "selector-condition", "level_mode": "server_start", "hint_level": 0,
        "turn_index": 0, "requested_hint_level": None, "request_payload": payload,
        "config_sha256": config["config_sha256"],
        "returned": {
            "question_id": case.tutor_context.question_id, "hint_level": 3, "baseline_hint_level": 3,
            "model": "generator-test", "hint": "Pruefe den Aufbau.", "stage": "hint", "policy_mode": "tutor",
            **config, "hint_policy": config["configuration"]["hint_policy"]["3"],
            "context_options": profile.flags(), "requested_context_options": profile.flags(),
            "prompt_messages": [{"role": "system", "content": "hint policy"}, {"role": "user", "content": content}],
            "start_decision": {"source": "model_hypothesis", "selected_level": 3,
                               "configuration_sha256": config["config_sha256"], "context_options": profile.flags()},
            "start_prompt_messages": [{"role": "system", "content": "selector policy"}, {"role": "user", "content": content}],
        },
    }
    return case, profile, generation


def test_selector_uses_observed_stage_zero_flags_not_effective_hint_flags(selector_evidence):
    case, profile, generation = selector_evidence
    configuration = generation["returned"]["configuration"]
    configuration["stage0_context_options"]["include_learning_goals"] = False
    generation["returned"]["start_decision"]["context_options"]["include_learning_goals"] = False
    generation["returned"]["start_prompt_messages"][-1]["content"] = generation["returned"]["start_prompt_messages"][-1]["content"].replace("GOAL_ONLY_MARKER", "")
    digest = configuration_sha256(configuration)
    generation["config_sha256"] = generation["returned"]["config_sha256"] = digest
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["start_selection_context"]["status"] == "pass"
    assert checks["context_options_match"]["status"] == "pass"
    assert checks["prompt_required_content"]["status"] == "pass"
    assert generation["returned"]["context_options"]["include_learning_goals"] is True


@pytest.mark.parametrize("field,marker", [
    ("question_text", "QUESTION_ONLY_MARKER"), ("student_answer", "STUDENT_ONLY_MARKER"),
    ("diagnosis_code", "DIAGNOSIS_ONLY_MARKER"), ("prt_feedback", "FEEDBACK_ONLY_MARKER"),
    ("score", "STACK-SCORE:\n0.0"), ("learning_goals", "GOAL_ONLY_MARKER"),
    ("math_rules", "RULE_ONLY_MARKER"),
])
def test_selector_detects_actual_disabled_context_even_when_reported_flags_match(selector_evidence, field, marker):
    case, profile, generation = selector_evidence
    flag = "include_" + field
    generation["returned"]["configuration"]["stage0_context_options"][flag] = False
    generation["returned"]["start_decision"]["context_options"][flag] = False
    assert marker in generation["returned"]["start_prompt_messages"][-1]["content"]
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["start_selection_context"]["status"] == "fail"
    assert field in checks["start_selection_context"]["evidence"]["leaked"]


@pytest.mark.parametrize("marker,part", [
    ("FINAL_ONLY_MARKER", "final_answer"), ("EQUIVALENT_ONLY_MARKER", "final_answer"),
    ("STEP_ONLY_MARKER", "solution_steps"),
])
def test_selector_disclosure_does_not_use_later_hint_policy_permissions(selector_evidence, marker, part):
    case, profile, generation = selector_evidence
    generation["returned"]["start_prompt_messages"][-1]["content"] += "\n" + marker
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["start_selection_context"]["status"] == "fail"
    assert part in checks["start_selection_context"]["evidence"]["leaked"]
    assert checks["prompt_solution_guard"]["status"] == "pass"


@pytest.mark.parametrize("flags", [
    None, {}, {"include_question_text": True}, {name: 1 for name in PROFILES["base"].flags()},
])
def test_selector_missing_or_incomplete_flags_remain_inconclusive(selector_evidence, flags):
    case, profile, generation = selector_evidence
    generation["returned"]["start_decision"]["context_options"] = flags
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "start_selection_context")
    assert check["status"] == "inconclusive"


def test_selector_missing_observed_prompt_is_never_reconstructed(selector_evidence):
    case, profile, generation = selector_evidence
    generation["returned"]["start_prompt_messages"] = None
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "start_selection_context")
    assert check["status"] == "inconclusive" and check["evidence"]["prompt_available"] is False


def test_selector_required_context_cannot_pass_with_only_policy_placeholder(selector_evidence):
    case, profile, generation = selector_evidence
    generation["returned"]["start_prompt_messages"][-1]["content"] = "Only policy, no selected case data."
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "start_selection_context")
    assert check["status"] == "fail"
    assert {"question_text", "student_answer", "score"} <= set(check["evidence"]["missing"])


def test_selector_flag_expansion_is_a_manipulation_failure(selector_evidence):
    case, profile, generation = selector_evidence
    generation["returned"]["start_decision"]["context_options"]["include_final_answer"] = True
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "start_selection_context")
    assert check["status"] == "fail" and "context_options" in check["evidence"]["leaked"]


@pytest.mark.parametrize("mode", ["model", "none"])
def test_selector_diagnosis_caps_can_reduce_requested_flags_without_false_failure(selector_evidence, mode):
    case, profile, generation = selector_evidence
    generation["returned"]["configuration"]["tutor_rules"]["diagnosis_mode"] = mode
    for field in ("diagnosis_code", "prt_feedback"):
        generation["returned"]["start_decision"]["context_options"]["include_" + field] = False
        generation["returned"]["context_options"]["include_" + field] = False
    for key in ("start_prompt_messages", "prompt_messages"):
        generation["returned"][key][-1]["content"] = generation["returned"][key][-1]["content"].replace("DIAGNOSIS_ONLY_MARKER", "").replace("FEEDBACK_ONLY_MARKER", "")
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["start_selection_context"]["status"] == "pass"
    assert checks["context_options_match"]["status"] == "pass"
    assert checks["prompt_required_content"]["status"] == "pass"


def test_server_context_raw_echo_is_checked_after_only_legitimate_diagnosis_cap(selector_evidence):
    case, profile, generation = selector_evidence
    generation["request_payload"].pop("context_options")
    generation["use_server_context"] = True
    generation["returned"]["configuration"]["tutor_rules"]["diagnosis_mode"] = "model"
    for field in ("diagnosis_code", "prt_feedback"):
        generation["returned"]["configuration"]["context_defaults"]["include_" + field] = False
        generation["returned"]["context_options"]["include_" + field] = False
        generation["returned"]["start_decision"]["context_options"]["include_" + field] = False
    for key in ("start_prompt_messages", "prompt_messages"):
        generation["returned"][key][-1]["content"] = generation["returned"][key][-1]["content"].replace("DIAGNOSIS_ONLY_MARKER", "").replace("FEEDBACK_ONLY_MARKER", "")
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["context_options_match"]["status"] == "pass"
    assert checks["start_selection_context"]["status"] == "pass"
    generation["returned"]["requested_context_options"]["include_math_rules"] = False
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["context_options_match"]["status"] == "fail"


def test_requested_options_must_match_even_when_effective_caps_hide_difference(selector_evidence):
    case, profile, generation = selector_evidence
    generation["returned"]["context_options"]["include_solution_steps"] = False
    generation["returned"]["requested_context_options"]["include_solution_steps"] = True
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "context_options_match")
    assert check["status"] == "fail"


@pytest.mark.parametrize("history_enabled", [False, True])
def test_current_history_turn_is_accepted_only_when_effective_history_is_enabled(selector_evidence, history_enabled):
    case, profile, generation = selector_evidence
    message = "CURRENT_ONLY_MARKER"
    generation.update(turn_index=1, stack_context=generation["request_payload"]["stack"], request_payload={
        "message": message, "context_options": {**profile.flags(), "include_chat_history": history_enabled},
    })
    generation["returned"]["context_options"]["include_chat_history"] = history_enabled
    generation["returned"]["requested_context_options"]["include_chat_history"] = history_enabled
    generation["returned"]["prompt_messages"].insert(1, {"role": "user", "content": message})
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "prompt_required_content")
    assert check["status"] == ("pass" if history_enabled else "fail")


def test_history_does_not_supply_missing_current_task_context_or_new_reference_sections(selector_evidence):
    case, profile, generation = selector_evidence
    generation.update(turn_index=1, stack_context=generation["request_payload"]["stack"], request_payload={
        "message": "CURRENT_ONLY_MARKER", "context_options": {**profile.flags(), "include_chat_history": True},
    })
    generation["returned"]["context_options"]["include_chat_history"] = True
    generation["returned"]["prompt_messages"][1:1] = [
        {"role": "user", "content": case.tutor_context.question_text},
        {"role": "assistant", "content": case.evaluation_only.reference.final_answer},
        {"role": "user", "content": "CURRENT_ONLY_MARKER"},
    ]
    generation["returned"]["prompt_messages"][-1]["content"] = generation["returned"]["prompt_messages"][-1]["content"].replace(case.tutor_context.question_text, "")
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["prompt_required_content"]["status"] == "fail"
    assert "question_text" in checks["prompt_required_content"]["evidence"]["missing"]
    assert "current_message" not in checks["prompt_required_content"]["evidence"]["missing"]
    assert checks["prompt_solution_guard"]["status"] == "pass"


def test_earlier_duplicate_user_message_does_not_satisfy_missing_current_history_turn(selector_evidence):
    case, profile, generation = selector_evidence
    generation.update(turn_index=2, stack_context=generation["request_payload"]["stack"], request_payload={
        "message": "CURRENT_ONLY_MARKER", "context_options": {**profile.flags(), "include_chat_history": True},
    })
    generation["returned"]["context_options"]["include_chat_history"] = True
    generation["returned"]["prompt_messages"][1:1] = [
        {"role": "user", "content": "CURRENT_ONLY_MARKER"},
        {"role": "assistant", "content": "Previous reply"},
        {"role": "user", "content": "Different previous request"},
    ]
    check = next(check for check in run_checks(generation, case, profile, POLICY) if check["check_id"] == "prompt_required_content")
    assert check["status"] == "fail" and "current_message" in check["evidence"]["missing"]


def test_correct_student_answer_inside_selector_is_not_reference_disclosure(selector_evidence):
    case, profile, generation = selector_evidence
    case.tutor_context.student_answer = case.evaluation_only.reference.final_answer
    generation["request_payload"]["stack"]["student_answer"] = case.tutor_context.student_answer
    for key in ("start_prompt_messages", "prompt_messages"):
        generation["returned"][key][-1]["content"] = generation["returned"][key][-1]["content"].replace("STUDENT_ONLY_MARKER", case.tutor_context.student_answer)
    checks = {check["check_id"]: check for check in run_checks(generation, case, profile, POLICY)}
    assert checks["start_selection_context"]["status"] == "pass"
    assert checks["prompt_solution_guard"]["status"] == "pass"


def test_report_retains_multiple_baselines_without_splitting_same_effective_group(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, cases=load_cases(DATA_DIR / "example_cases.jsonl")[:2],
                       level_mode="server_start", hint_levels=[0])
    execute(run_dir, TutorTransport(config, levels=[2]))
    records = read_records(run_dir / "generations.jsonl")
    for record, baseline in zip(records, (0, 1)):
        record["returned"]["baseline_hint_level"] = baseline
    write_records(run_dir / "generations.jsonl", records)
    assert build_report(run_dir)["summary_rows"] == 1
    with (run_dir / "derived" / "summary.csv").open(encoding="utf-8") as handle:
        summary = next(csv.DictReader(handle))
    assert json.loads(summary["baseline_hint_levels"]) == [0, 1]
    assert summary["n_success"] == "2" and summary["effective_hint_level"] == "2"


def test_missing_baseline_remains_unknown_not_the_server_start_placeholder(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, level_mode="server_start", hint_levels=[0])
    execute(run_dir, TutorTransport(config, levels=[2]))
    records = read_records(run_dir / "generations.jsonl")
    records[0]["returned"].pop("baseline_hint_level")
    write_records(run_dir / "generations.jsonl", records)
    build_report(run_dir)
    with (run_dir / "derived" / "summary.csv").open(encoding="utf-8") as handle:
        summary = next(csv.DictReader(handle))
    assert json.loads(summary["baseline_hint_levels"]) == [None]


def test_cross_condition_comparison_keeps_baselines_as_outcome_columns_not_keys(tmp_path):
    config = public_config()
    baseline = make_run(tmp_path, "fixed-baseline", config=config, condition_id="fixed", level_mode="server_start", hint_levels=[0])
    candidate = make_run(tmp_path, "individual-baseline", config=config, condition_id="individual", level_mode="server_start", hint_levels=[0])
    execute(baseline, TutorTransport(config, levels=[0]))
    execute(candidate, TutorTransport(config, levels=[2]))
    comparison = compare_runs([baseline, candidate])
    assert comparison["coverage"]["paired_responses"] == 1
    row = comparison["paired_rows"][0]
    assert row["reference_baseline_hint_level"] == 0 and row["baseline_hint_level"] == 2
    assert row["reference_stage"] == "diagnostic" and row["stage"] == "hint"
    assert row["start_level"] == "server_start"


def test_profile_pair_keeps_different_observed_baselines(tmp_path):
    config = public_config()
    run_dir = make_run(tmp_path, config=config, profiles=["base", "diagnosis"], level_mode="server_start", hint_levels=[0])
    execute(run_dir, TutorTransport(config, levels=[2]))
    records = read_records(run_dir / "generations.jsonl")
    for record in records:
        record["returned"]["baseline_hint_level"] = 0 if record["profile_id"] == "base" else 1
    write_records(run_dir / "generations.jsonl", records)
    rate_packet(run_dir, 4)
    assert build_report(run_dir)["paired_rows"] == 1
    with (run_dir / "derived" / "paired_comparisons.csv").open(encoding="utf-8") as handle:
        pair = next(csv.DictReader(handle))
    assert pair["base_baseline_hint_level"] == "0" and pair["baseline_hint_level"] == "1"


def test_actual_api_active_config_selector_evidence_and_credentials_roundtrip(monkeypatch, chat_store):
    from fastapi.testclient import TestClient
    from app import config, main
    from app.database import initialize_database
    import requests

    calls = []
    token = "conditions-test-only-token"

    class FakeLLM:
        def chat(self, messages, **kwargs):
            calls.append(copy.deepcopy(messages))
            if kwargs.get("json_output"):
                return json.dumps({"hint_level": 1, "reason": "Uncertain synthetic support decision"})
            return "Welche Struktur erkennst du?"

    monkeypatch.setattr(main, "CHAT_STORE", chat_store)
    monkeypatch.setattr(main, "initialize_database", lambda: initialize_database(chat_store.database_path))
    monkeypatch.setattr(main, "create_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(config, "TUTOR_START_MODE", "individual")
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "provided")
    monkeypatch.setattr(config, "TUTOR_RESPONSE_FORMAT", "text")
    monkeypatch.setattr(config, "EVALUATION_API_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_API_TOKEN", token)
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", token)
    monkeypatch.setenv("TUTOR_LEVEL_1_MAX_WORDS", "9")
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *args, **kwargs: pytest.fail("External network is forbidden"))
    profile = PROFILES["base"]
    payload = build_request_payload(CASE, profile, None, main.LLM_MODEL)
    payload["stack"]["learning_goals"] = ["HIDDEN_SELECTOR_GOAL"]
    with TestClient(main.app) as client:
        assert client.get("/api/evaluation/config").status_code == 401
        observed = client.get("/api/evaluation/config", headers={"X-Evaluation-Token": token}).json()
        assert observed["config_sha256"] == client.get("/health").json()["config_sha256"]
        assert observed["configuration"]["hint_policy"] == main.HINT_POLICY.levels
        assert validate_public_configuration(observed)["config_sha256"] == observed["config_sha256"]
        response = client.post("/api/tutor/start", json=payload)
        assert response.status_code == 200
        returned = response.json()
    assert token not in json.dumps(observed) and token not in json.dumps(returned)
    assert "HIDDEN_SELECTOR_GOAL" not in json.dumps(returned["start_prompt_messages"])
    assert returned["start_prompt_messages"] == calls[0]
    assert returned["start_decision"]["context_options"] == returned["context_options"]
    generation = {
        "outcome": "success", "level_mode": "server_start", "turn_index": 0, "requested_hint_level": None,
        "request_payload": payload, "returned": returned, "config_sha256": observed["config_sha256"],
    }
    checks = {check["check_id"]: check for check in run_checks(generation, CASE, profile, POLICY)}
    for check_id in ("configuration_identity", "context_options_match", "prompt_required_content", "start_selection_context"):
        assert checks[check_id]["status"] == "pass"
