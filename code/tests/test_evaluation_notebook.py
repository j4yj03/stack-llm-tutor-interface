"""Notebook preparation, offline demo and mocked live workflow."""

import ast
import builtins
import copy
import csv
import json
import shutil
import uuid
from pathlib import Path

import pytest

from evaluation import judge as judge_module, report as report_module, runner as runner_module
from evaluation.checks import run_checks_for_run
from evaluation.corpus import configuration_sha256, load_cases, load_profiles, sha256_file
from evaluation.models import PROFILE_FLAG_NAMES
from evaluation.notebook import (
    fetch_server_configuration,
    load_expected_configuration,
    prepare_run,
    preview_messages,
    read_jsonl,
    verify_notebook_inputs,
    write_demo_results,
)
from evaluation.task_cases import cases_from_tasks, task_source_hashes
from evaluation.report import build_report, export_review_packet
from evaluation.runner import CODE_DIR, Runner, RunnerError, load_plan

EVAL_DIR = CODE_DIR / "evaluation"
NOTEBOOK_PATH = EVAL_DIR / "notebooks" / "testbench.ipynb"


@pytest.fixture
def run_options(tmp_path):
    flags = {name: False for name in PROFILE_FLAG_NAMES}
    flags.update(include_question_text=True, include_student_answer=True)
    return {
        "run_dir": tmp_path / "demo-001",
        "corpus_path": EVAL_DIR / "data" / "example_cases.jsonl",
        "profiles_path": EVAL_DIR / "data" / "context_profiles.json",
        "case_ids": ["chain-exp-missing-inner-001", "prod-missing-term-002"],
        "profile_ids": ["base", "custom"],
        "custom_flags": flags,
        "hint_levels": [1, 3],
        "model": None,
        "mode": "demo",
        "base_url": "http://tutor.test",
    }


def test_plan_freezes_selected_inputs_and_rejects_changed_configuration(run_options):
    manifest = prepare_run(**run_options)
    run_dir = run_options["run_dir"]
    assert manifest["execution_mode"] == "offline_demo"
    assert manifest["counts"]["jobs"] == 8
    assert len(load_cases(CODE_DIR / manifest["paths"]["corpus"])) == 2
    assert len(load_profiles(CODE_DIR / manifest["paths"]["profiles"]).profiles) == 2
    assert prepare_run(**run_options) == manifest
    original_plan = (run_dir / "plan.jsonl").read_bytes()
    with pytest.raises(RunnerError, match="Konfiguration geaendert"):
        prepare_run(**{**run_options, "hint_levels": [4]})
    assert (run_dir / "plan.jsonl").read_bytes() == original_plan
    assert not (run_dir / "generations.jsonl").exists()


@pytest.mark.parametrize("changes", [
    {"mode": "invalid"},
    {"mode": "live", "model": None},
    {"case_ids": ["unknown-case"]},
    {"profile_ids": ["unknown-profile"]},
    {"profile_ids": []},
    {"hint_levels": []},
    {"allow_unverified_cases": False},
])
def test_invalid_selection_writes_no_run(run_options, changes):
    with pytest.raises(ValueError):
        prepare_run(**{**run_options, **changes})
    assert not run_options["run_dir"].exists()


def test_empty_case_filter_selects_all_and_history_is_rejected(run_options):
    manifest = prepare_run(**{**run_options, "case_ids": []})
    assert manifest["counts"]["cases"] == 12
    flags = {**run_options["custom_flags"], "include_chat_history": True}
    with pytest.raises(ValueError, match="Historie"):
        prepare_run(**{**run_options, "custom_flags": flags})


def test_demo_checks_are_visible_but_excluded_from_quality_reporting(
    run_options, monkeypatch,
):
    import requests

    def forbid_network(*args, **kwargs):
        pytest.fail("Offline demo must not make a network request")

    monkeypatch.setattr(requests.sessions.Session, "request", forbid_network)
    prepare_run(**run_options)
    run_dir = run_options["run_dir"]
    records = write_demo_results(run_dir)
    assert write_demo_results(run_dir) == records
    assert len(records) == 8
    assert all(record["execution_source"] == "offline_demo" for record in records)
    assert all(record["duration_ms"] is None for record in records)
    assert all(record["returned"]["model"] == "offline-demo-kein-llm" for record in records)
    run_checks_for_run(run_dir)
    assert any(
        check["check_id"] == "final_answer_disclosure" and check["status"] == "fail"
        for check in read_jsonl(run_dir / "checks.jsonl")
    )
    assert export_review_packet(run_dir)["packet_rows"] == 0
    report = build_report(run_dir)
    assert report["coverage"]["generations_total"] == 0
    assert report["coverage"]["checks_total"] == 0
    with pytest.raises(RunnerError, match="Demolauf"):
        Runner(run_dir).run(execute_live=True)


def test_preview_uses_the_real_double_guard(run_options):
    prepare_run(**{**run_options, "profile_ids": ["solution"], "hint_levels": [1, 3, 4]})
    for job in load_plan(run_options["run_dir"]):
        payload = job["request_payload"]
        assert payload["stack"]["final_answer"]
        messages = preview_messages(payload)
        user_content = messages[-1]["content"]
        assert ("MUSTERL\u00d6SUNG" in user_content) == (job["hint_level"] == 4)
        assert ("L\u00d6SUNGSSCHRITTE" in user_content) == (job["hint_level"] >= 3)


def test_demo_cannot_overwrite_live_run(run_options):
    prepare_run(**{**run_options, "mode": "live", "model": "test-model"})
    with pytest.raises(RunnerError, match="Demolauf"):
        write_demo_results(run_options["run_dir"])
    assert not (run_options["run_dir"] / "generations.jsonl").exists()


def execute_cells(monkeypatch, tmp_path, overrides=None):
    """Execute trusted repository cells; notebook dependencies stay optional."""
    pytest.importorskip("pandas")
    pytest.importorskip("ipywidgets")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: plt.close("all"))
    monkeypatch.setenv("TUTOR_EVALUATION_RUNS", str(tmp_path))
    monkeypatch.chdir(NOTEBOOK_PATH.parent)
    document = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__"}
    for cell in document["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = cell["source"]
        source = source if isinstance(source, str) else "".join(source)
        exec(compile(source, str(NOTEBOOK_PATH) + "#" + cell["id"], "exec"), namespace)
        if cell["id"] == "configuration" and overrides:
            namespace.update(overrides)
            namespace["run_dir"] = namespace["RUN_ROOT"] / namespace["RUN_ID"]
    return namespace, document


def test_notebook_run_all_is_offline_from_its_own_directory(monkeypatch, tmp_path):
    import requests

    def forbid_network(*args, **kwargs):
        pytest.fail("Default notebook execution must remain offline")

    monkeypatch.setattr(requests.sessions.Session, "request", forbid_network)
    namespace, document = execute_cells(monkeypatch, tmp_path)
    assert namespace["MODE"] == "demo"
    assert len(namespace["generations"]) == 24
    assert len(namespace["result_df"]) == 24
    assert namespace["report_result"]["coverage"]["responses_total"] == 0
    assert (namespace["derived_dir"] / "automatic_checks.png").is_file()
    assert (namespace["derived_dir"] / "ausgaben.csv").is_file()
    assert namespace["review_rows"] == []
    assert namespace["CASE_SOURCE"] == "tasks"
    assert namespace["manifest"]["case_source"] == "tasks"
    assert namespace["HINT_LEVELS"] == [0, 1]
    assert namespace["CUSTOM_FLAGS"]["include_math_rules"] is False
    assert namespace["manifest"]["counts"]["sessions"] == 24
    assert namespace["judge_result"] is None
    assert not (namespace["run_dir"] / "reviews" / "judge").exists()
    assert len(namespace["manifest"]["source_task_hashes"]) == 2
    assert set(namespace["result_df"]["stage"]) == {"diagnostic", "hint"}
    assert all(cell.get("outputs", []) == [] for cell in document["cells"])
    assert all(cell.get("execution_count") is None for cell in document["cells"])


def test_analysis_uses_snapshots_instead_of_original_files(monkeypatch, tmp_path):
    execute_cells(monkeypatch, tmp_path)
    namespace, _ = execute_cells(monkeypatch, tmp_path, {
        "MODE": "analyze", "CORPUS_FILE": tmp_path / "missing-corpus.jsonl",
        "PROFILES_FILE": tmp_path / "missing-profiles.json", "CASE_IDS": ["gone-case"],
        "PROFILE_IDS": ["gone-profile"],
        "TASKS_DIR": tmp_path / "missing-tasks", "TASK_SCHEMA_PATH": tmp_path / "missing-schema",
        "EXPECTED_CONFIG_FILE": tmp_path / "missing-config.json", "FETCH_SERVER_CONFIGURATION": True,
        "EXECUTE_LIVE": True, "EXECUTE_JUDGE_LIVE": True,
    })
    assert len(namespace["generations"]) == 24
    assert namespace["is_demo"] is True
    assert namespace["case_selector"].disabled
    assert namespace["preview_messages"] is preview_messages


def test_mocked_live_notebook_supports_ratings_and_paired_analysis(monkeypatch, tmp_path):
    calls = []
    budget_clock = [0.0]
    original_init = Runner.__init__

    def simulated_sleep(seconds):
        budget_clock[0] += seconds

    def offline_init(self, *args, **kwargs):
        original_init(self, *args, sleep=simulated_sleep, clock=lambda: budget_clock[0], **kwargs)

    # The 24-job grid exceeds the weighted 20-generator/hour default.
    monkeypatch.setattr(Runner, "__init__", offline_init)

    def transport(method, url, payload, timeout):
        if method == "GET":
            return 200, {"default_model": "test-model", "tasks_loaded": 2}, None, ""
        calls.append(payload)
        return 200, {
            "chat_id": str(uuid.UUID(int=len(calls))),
            "question_id": payload["stack"]["question_id"],
            "hint_level": payload["hint_level"],
            "model": payload["model"],
            "hint": "Welche Ableitungsregel hilft dir bei diesem eigenen Schritt?",
            "context_options": payload["context_options"],
            "prompt_messages": preview_messages(payload),
        }, None, ""

    monkeypatch.setattr(runner_module, "_request_transport", transport)
    namespace, document = execute_cells(monkeypatch, tmp_path, {
        "MODE": "live", "MODEL": "test-model", "EXECUTE_LIVE": True, "RUN_ID": "mock-live-001",
    })
    assert len(calls) == len(namespace["review_rows"]) == 24
    assert namespace["report_result"]["coverage"]["responses_missing_ratings"] == 24
    mapping = json.loads(
        (namespace["run_dir"] / "reviews" / "review_mapping.json").read_text(encoding="utf-8")
    )["mapping"]
    for profile_id, value in [("base", "3"), ("custom", "5")]:
        review_id = next(
            key for key, item in mapping.items()
            if item["case_id"] == "task-chain-exp-missing-inner-001"
            and item["hint_level"] == 1 and item["profile_id"] == profile_id
        )
        namespace["review_selector"].value = review_id
        namespace["rater_field"].value = "expert-1"
        namespace["rating_fields"]["hilfreichkeit_naechster_schritt"].value = value
        namespace["save_button"].click()
    for cell in document["cells"]:
        if cell["id"] in {"report", "rating-plot"}:
            exec("".join(cell["source"]), namespace)
    assert namespace["report_result"]["coverage"]["responses_with_ratings"] == 2
    assert len(namespace["paired_df"]) == 1
    assert namespace["paired_df"]["delta"].iloc[0] == 2
    assert (namespace["derived_dir"] / "ratings.png").is_file()


@pytest.fixture
def task_options(run_options, tmp_path):
    tasks_dir = tmp_path / "authored-tasks"
    tasks_dir.mkdir()
    for source in (CODE_DIR / "tasks").glob("*.json"):
        (tasks_dir / source.name).write_bytes(source.read_bytes())
    schema_path = tmp_path / "task-schema.json"
    schema_path.write_bytes((CODE_DIR / "schemas" / "stack_ai_tutor_task.schema.json").read_bytes())
    return {
        **run_options, "corpus_path": None, "tasks_dir": tasks_dir, "task_schema_path": schema_path,
        "case_ids": ["task-chain-exp-missing-inner-001", "task-prod-missing-term-001"],
        "hint_levels": [0, 1], "allow_task_derived_cases": True,
    }


def public_snapshot(**rules):
    policy = json.loads((CODE_DIR / "config" / "hint_levels.json").read_text(encoding="utf-8"))
    flags = {name: name in {"include_question_text", "include_student_answer"} for name in PROFILE_FLAG_NAMES}
    configuration = {
        "schema_version": "tutor-config-1", "hint_policy": policy,
        "generation": {"model": "test-model", "temperature": 0.2, "max_tokens": 400},
        "start": {"mode": "individual", "level": 1, "min_level": 0, "max_level": 4},
        "tutor_rules": {"policy_mode": "tutor", "diagnosis_mode": "provided", "rules_id": "notebook-test",
                        "enforce_word_limit": True, "hide_hint_level": True, **rules},
        "context_defaults": flags, "stage0_context_options": flags,
        "adaptation": {"enabled": True, "after_seconds": 120, "step": 1, "max_level": 4},
    }
    return {
        "configuration": configuration, "config_sha256": configuration_sha256(configuration),
        "rule_id": "judge-rubric-1.0-v2", "judge_model": "judge-model",
        "judge_parameters": {"temperature": 0.0, "max_tokens": 1200, "json_output": True},
    }


def execute_cell(namespace, cell_id):
    document = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell = next(cell for cell in document["cells"] if cell["id"] == cell_id)
    source = cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
    exec(compile(source, str(NOTEBOOK_PATH) + "#" + cell_id, "exec"), namespace)


def test_task_preparation_freezes_selected_tasks_schema_and_all_conditions(task_options):
    snapshot = public_snapshot()
    manifest = prepare_run(**task_options, condition_id="task-fixed", expected_config=snapshot,
                           request_budget_units_per_hour=60)
    run_dir = task_options["run_dir"]
    assert manifest["source_task_hashes"] == task_source_hashes(task_options["tasks_dir"], task_options["task_schema_path"])
    for source, digest in manifest["source_task_hashes"].items():
        assert sha256_file(run_dir / "inputs" / source) == digest
    assert (run_dir / "inputs" / "schemas" / "stack_ai_tutor_task.schema.json").read_bytes() == task_options["task_schema_path"].read_bytes()
    exp = json.loads((run_dir / "inputs" / "experiment.json").read_text(encoding="utf-8"))
    assert exp["condition_id"] == "task-fixed" and exp["allow_task_derived_cases"] is True
    assert exp["request_budget_units_per_hour"] == 60
    assert exp["expected_config_sha256"] == snapshot["config_sha256"]
    cases = load_cases(run_dir / "inputs" / "cases.jsonl")
    assert all(case.tutor_context.diagnosis_source == "synthetic" for case in cases)
    assert all(case.tutor_context.math_rules == [] and case.tutor_context.score is None for case in cases)
    assert all(case.evaluation_only.provenance.response_origin == "synthetic_fixture" for case in cases)
    assert all(case.evaluation_only.verification.mathematics_status == "pending" for case in cases)
    assert prepare_run(**task_options, condition_id="task-fixed", expected_config=snapshot,
                       request_budget_units_per_hour=60) == manifest


def test_selected_task_snapshot_does_not_require_originals(task_options):
    manifest = prepare_run(**task_options)
    shutil.rmtree(task_options["tasks_dir"])
    task_options["task_schema_path"].unlink()
    assert verify_notebook_inputs(task_options["run_dir"]) == manifest
    assert len(write_demo_results(task_options["run_dir"])) == 8


def test_task_preparation_snapshots_only_selected_task_sources(task_options):
    manifest = prepare_run(**{**task_options, "case_ids": ["task-chain-exp-missing-inner-001"]})
    assert set(manifest["source_task_hashes"]) == {"tasks/ableitung_kettenregel_exp_001.json"}
    assert len(list((task_options["run_dir"] / "inputs" / "tasks").glob("*.json"))) == 1


@pytest.mark.parametrize("field", ["task", "schema", "expected_configuration"])
def test_changed_frozen_source_is_rejected(task_options, field):
    manifest = prepare_run(**task_options, expected_config=public_snapshot())
    paths = {
        "task": task_options["run_dir"] / "inputs" / next(iter(manifest["source_task_hashes"])),
        "schema": task_options["run_dir"] / "inputs" / "schemas" / "stack_ai_tutor_task.schema.json",
        "expected_configuration": task_options["run_dir"] / "inputs" / "expected_configuration.json",
    }
    path = paths[field]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(RunnerError, match="Frozen notebook input"):
        verify_notebook_inputs(task_options["run_dir"])


def test_manifest_configuration_must_match_frozen_full_snapshot(task_options):
    prepare_run(**task_options, expected_config=public_snapshot())
    path = task_options["run_dir"] / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["expected_configuration"]["judge_model"] = "different-judge"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RunnerError, match="frozen snapshot"):
        verify_notebook_inputs(task_options["run_dir"])


def test_changed_task_source_requires_new_run_even_if_selected_case_unchanged(task_options):
    prepare_run(**task_options)
    path = next(task_options["tasks_dir"].glob("*.json"))
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(RunnerError, match="Konfiguration geaendert"):
        prepare_run(**task_options)


@pytest.mark.parametrize("field,value", [
    ("condition_id", "changed"), ("use_server_context", True),
    ("interaction_script", [{"message": "continue", "elapsed_seconds": 120}]),
    ("request_budget_units_per_hour", 40),
])
def test_condition_changes_never_overwrite_notebook_run(task_options, field, value):
    prepare_run(**task_options)
    before = (task_options["run_dir"] / "plan.jsonl").read_bytes()
    with pytest.raises(RunnerError, match="Konfiguration geaendert"):
        prepare_run(**{**task_options, field: value})
    assert (task_options["run_dir"] / "plan.jsonl").read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"allow_task_derived_cases": False}, {"allow_unverified_cases": False},
    {"level_mode": "server_start", "hint_levels": [0, 1]},
    {"expected_config": {"configuration": {}, "config_sha256": "0" * 64}},
])
def test_invalid_task_conditions_write_no_run(task_options, changes):
    with pytest.raises(ValueError):
        prepare_run(**{**task_options, **changes})
    assert not task_options["run_dir"].exists()


def test_history_is_allowed_only_for_scripted_sessions(task_options):
    flags = {**task_options["custom_flags"], "include_chat_history": True}
    script = [{"message": "I do not understand", "elapsed_seconds": 150, "confusion_signal": True}]
    manifest = prepare_run(**{**task_options, "custom_flags": flags, "interaction_script": script})
    jobs = load_plan(task_options["run_dir"])
    assert manifest["counts"]["jobs"] == 16
    assert jobs[1]["turn_index"] == 1 and jobs[1]["depends_on_job_id"] == jobs[0]["job_id"]
    assert jobs[1]["request_payload"]["simulation_elapsed_seconds"] == 150
    assert "student_answer" not in jobs[1]["request_payload"]
    assert jobs[1]["stack_context"]["student_answer"] == jobs[0]["request_payload"]["stack"]["student_answer"]


def test_server_start_demo_never_invents_individual_selection(task_options):
    prepare_run(**{**task_options, "hint_levels": [0], "level_mode": "server_start", "expected_config": public_snapshot(),
                   "interaction_script": [{"message": "continue", "elapsed_seconds": 300}]})
    records = write_demo_results(task_options["run_dir"])
    assert len(records) == 8
    assert all(record["outcome"] == "not_executed" and record["returned"] is None for record in records)
    assert all(record["effective_hint_level"] is None and record["duration_ms"] is None for record in records)
    assert build_report(task_options["run_dir"])["coverage"]["responses_total"] == 0


def test_scripted_demo_keeps_fixed_levels_without_adaptation(task_options):
    prepare_run(**{**task_options, "hint_levels": [0], "interaction_script": [
        {"message": "I do not understand", "elapsed_seconds": 300, "confusion_signal": True},
        {"message": "More please", "hint_level": 1},
    ]})
    records = write_demo_results(task_options["run_dir"])
    assert [record["effective_hint_level"] for record in records[:3]] == [0, 0, 1]
    assert all(record["returned"]["adaptation"] is None and record["returned"]["llm_operations"] is None for record in records)
    assert all(record["returned"]["prompt_messages"] == [] for record in records if record["turn_index"])


def test_demo_active_policy_snapshot_is_not_a_server_observation(task_options):
    snapshot = public_snapshot()
    snapshot["configuration"]["hint_policy"]["0"]["max_words"] = 30
    snapshot["config_sha256"] = configuration_sha256(snapshot["configuration"])
    prepare_run(**task_options, expected_config=snapshot)
    records = write_demo_results(task_options["run_dir"])
    diagnostic = next(record for record in records if record["effective_hint_level"] == 0)
    assert diagnostic["returned"]["hint_policy"]["max_words"] == 30
    assert diagnostic["returned"]["policy_origin"] == "offline_snapshot_not_observed"
    assert diagnostic["returned"]["prompt_messages"] is None


def test_preview_is_absent_for_unknown_start_defaults_and_followups():
    assert preview_messages({"stack": {}, "hint_level": None}) == []
    assert preview_messages({"stack": {"question_id": "x"}, "hint_level": 1}) == []
    assert preview_messages({"message": "continue", "hint_level": 1, "context_options": {}}) == []


@pytest.mark.parametrize("mode,fetch", [("demo", True), ("analyze", True), ("live", False)])
def test_configuration_read_gate_does_not_touch_network(mode, fetch):
    def forbidden(*args):
        pytest.fail("Configuration gate must not dispatch")

    assert fetch_server_configuration("http://tutor.test", mode=mode, fetch=fetch, transport=forbidden) is None


def test_configuration_fetch_and_offline_load_keep_only_public_fields(tmp_path, monkeypatch):
    snapshot = public_snapshot()
    calls = []
    token = "never-recorded-notebook-token"
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", token)

    def transport(method, url, payload, timeout):
        calls.append((method, url, payload))
        return 200, {**snapshot, "authorization": token, "extra": "discard"}, None, ""

    returned = fetch_server_configuration("http://tutor.test", mode="live", fetch=True, transport=transport)
    assert returned == snapshot and calls == [("GET", "http://tutor.test/api/evaluation/config", None)]
    assert token not in json.dumps(returned)
    path = tmp_path / "public.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert load_expected_configuration(path) == snapshot


def test_configuration_fetch_uses_transport_header_without_logging_token(monkeypatch):
    import requests

    snapshot = public_snapshot()
    calls = []
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", "private-test-token")

    class Response:
        status_code = 200

        def json(self):
            return snapshot

    def get(url, **kwargs):
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(requests, "get", get)
    assert fetch_server_configuration("http://tutor.test", mode="live", fetch=True) == snapshot
    assert calls[0]["headers"] == {"X-Evaluation-Token": "private-test-token"}
    assert calls[0]["verify"] is True and calls[0]["allow_redirects"] is False


@pytest.mark.parametrize("status,body", [(401, {"detail": "private-key"}), (200, {"configuration": {}, "config_sha256": "0" * 64})])
def test_configuration_errors_never_expose_upstream_text(status, body):
    with pytest.raises(RunnerError) as raised:
        fetch_server_configuration("http://tutor.test", mode="live", fetch=True,
                                   transport=lambda *args: (status, body, None, "private-key"))
    assert "private-key" not in str(raised.value)


def test_public_judge_metadata_cannot_echo_local_credential(monkeypatch):
    snapshot = public_snapshot()
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", "private-evaluation-credential")
    snapshot["judge_model"] = "private-evaluation-credential"
    with pytest.raises(RunnerError, match="Invalid public"):
        fetch_server_configuration("http://tutor.test", mode="live", fetch=True,
                                   transport=lambda *args: (200, snapshot, None, ""))


def test_notebook_run_all_does_not_import_main_database_or_create_llm(monkeypatch, tmp_path):
    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name in {"app.main", "app.database", "app.chat_store", "app.llm", "app.llm.factory"}:
            pytest.fail("Notebook imported side-effectful server module " + name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    namespace, _document = execute_cells(monkeypatch, tmp_path, {
        "FETCH_SERVER_CONFIGURATION": True, "EXECUTE_JUDGE_LIVE": True,
    })
    assert namespace["is_demo"] and namespace["judge_result"] is None


def test_notebook_syntax_outputs_and_ids_are_valid():
    nbformat = pytest.importorskip("nbformat")
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    ids = [cell["id"] for cell in notebook["cells"]]
    assert len(ids) == len(set(ids))
    assert {"judge", "condition-comparison"} <= set(ids)
    ast.parse((CODE_DIR / "evaluation" / "notebook.py").read_text(encoding="utf-8"), feature_version=(3, 11))
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse(cell["source"], feature_version=(3, 11))
            assert cell["outputs"] == [] and cell["execution_count"] is None


@pytest.fixture
def mocked_tutor(monkeypatch):
    snapshot = public_snapshot()
    sessions = {}
    calls = []
    monkeypatch.setenv("TUTOR_EVALUATION_TOKEN", "test-only-notebook-credential")

    def transport(method, url, payload, timeout):
        calls.append((method, url, copy.deepcopy(payload)))
        if url.endswith("/health"):
            return 200, {"default_model": "test-model", "tasks_loaded": 2, "config_sha256": snapshot["config_sha256"]}, None, ""
        if url.endswith("/api/evaluation/config"):
            return 200, snapshot, None, ""
        if url.endswith("/start"):
            chat_id = str(uuid.UUID(int=len(sessions) + 1))
            level = payload["hint_level"] if payload.get("hint_level") is not None else 0
            sessions[chat_id] = {"stack": payload["stack"], "level": level, "baseline": level}
        else:
            chat_id = url.rsplit("/", 2)[1]
            session = sessions[chat_id]
            previous = session["level"]
            level = payload.get("hint_level")
            if level is None:
                level = previous + int(payload.get("simulation_elapsed_seconds", 0) >= 120 and payload.get("confusion_signal") is True)
            session["level"] = level
        session = sessions[chat_id]
        options = dict(payload.get("context_options", snapshot["configuration"]["context_defaults"]))
        if level == 0:
            options = {key: enabled and snapshot["configuration"]["stage0_context_options"][key] for key, enabled in options.items()}
        content = []
        for name in ("question_text", "student_answer", "diagnosis_code", "prt_feedback"):
            value = session["stack"].get(name)
            if options["include_" + name] and value:
                content.append("<" + name + ">\n" + value + "\n</" + name + ">")
        if options["include_learning_goals"]:
            content.extend(session["stack"]["learning_goals"])
        if payload.get("message"):
            content.append("<current_message>\n" + payload["message"] + "\n</current_message>")
        hypothesis = "Hypothesis, not PRT evidence" if snapshot["configuration"]["tutor_rules"]["diagnosis_mode"] == "model" else None
        returned = {
            "chat_id": chat_id, "question_id": session["stack"]["question_id"], "hint_level": level,
            "baseline_hint_level": session["baseline"], "model": "test-model",
            "hint": "Welche Regel hast du bisher angewendet?", "diagnosis_hypothesis": hypothesis,
            "stage": "diagnostic" if level == 0 else "hint", "policy_mode": "tutor",
            "hint_policy": snapshot["configuration"]["hint_policy"][str(level)],
            "configuration": snapshot["configuration"], "config_sha256": snapshot["config_sha256"],
            "prompt_messages": [{"role": "system", "content": "Actual mocked policy"}, {"role": "user", "content": "\n".join(content)}],
            "context_options": options, "start_decision": {"mode": "individual", "chosen_level": session["baseline"]},
            "start_prompt_messages": [{"role": "system", "content": "Actual mocked start selection"}],
            "adaptation": {"reason": "time_and_confusion" if level > session["baseline"] else "no_corroborating_signal",
                           "elapsed_seconds": payload.get("simulation_elapsed_seconds"), "time_source": "simulation",
                           "applied": level > session["baseline"]},
            "llm_operations": 2 if url.endswith("/start") and payload.get("hint_level") is None else 1,
        }
        return 200, returned, None, ""

    monkeypatch.setattr(runner_module, "_request_transport", transport)
    return snapshot, calls


def small_live_overrides(**values):
    return {
        "MODE": "live", "EXECUTE_LIVE": True, "MODEL": "test-model", "RUN_ID": "live-small",
        "CASE_IDS": ["task-chain-exp-missing-inner-001"], "PROFILE_IDS": ["base"], "HINT_LEVELS": [0, 1],
        **values,
    }


def test_notebook_explicit_config_read_without_generation(monkeypatch, tmp_path, mocked_tutor):
    snapshot, calls = mocked_tutor
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(
        EXECUTE_LIVE=False, FETCH_SERVER_CONFIGURATION=True,
    ))
    assert [(method, url.rsplit("/", 1)[-1]) for method, url, _payload in calls] == [("GET", "config")]
    assert namespace["manifest"]["expected_config_sha256"] == snapshot["config_sha256"]
    assert namespace["manifest"]["expected_configuration"]["judge_model"] == "judge-model"
    assert namespace["generations"] == []
    assert namespace["result_df"]["outcome"].eq("not_executed").all()
    assert not (namespace["run_dir"] / "generations.jsonl").exists()


def test_notebook_config_file_pins_live_preflight_and_no_implicit_read(monkeypatch, tmp_path, mocked_tutor):
    snapshot, calls = mocked_tutor
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(EXPECTED_CONFIG_FILE=path))
    assert namespace["manifest"]["runtime"]["config_sha256"] == snapshot["config_sha256"]
    assert len([call for call in calls if call[1].endswith("/api/evaluation/config")]) == 1
    assert namespace["result_df"]["policy_origin"].eq("observed_response").all()
    assert namespace["result_df"]["baseline_hint_level"].notna().all()
    assert (namespace["derived_dir"] / "configuration_evidence.json").exists()


def test_notebook_server_start_script_uses_effective_outcomes_and_fixed_answer(monkeypatch, tmp_path, mocked_tutor):
    snapshot, calls = mocked_tutor
    script = [
        {"message": "Please continue", "elapsed_seconds": 180, "confusion_signal": False},
        {"message": "I do not understand", "elapsed_seconds": 180, "confusion_signal": True},
    ]
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(
        HINT_LEVELS=[0], LEVEL_MODE="server_start", USE_SERVER_CONTEXT=True,
        CONDITION_ID="individual-adaptive", INTERACTION_SCRIPT=script,
    ))
    requests = [payload for method, _url, payload in calls if method == "POST"]
    assert len(requests) == 3 and requests[0]["hint_level"] is None
    assert all("context_options" not in payload for payload in requests)
    assert all("stack" not in payload and "student_answer" not in payload for payload in requests[1:])
    table = namespace["result_df"]
    assert table["effective_hint_level"].tolist() == [0, 0, 1]
    assert table["turn_index"].tolist() == [0, 1, 2]
    assert table["stage"].tolist() == ["diagnostic", "diagnostic", "hint"]
    assert table["condition_id"].eq("individual-adaptive").all()
    assert table["student_answer"].nunique() == 1
    assert table.iloc[-1]["adaptation_reason"] == "time_and_confusion"
    assert table.iloc[-1]["scripted_elapsed_seconds"] == 180
    assert table["config_sha256"].eq(snapshot["config_sha256"]).all()
    assert namespace["checks_df"]["status"].ne("fail").all()
    assert namespace["level_selector"].disabled
    assert not namespace["flag_widgets"]["include_chat_history"].disabled


def test_live_notebook_without_any_gate_has_no_network(monkeypatch, tmp_path):
    def forbidden(*args):
        pytest.fail("Unapproved notebook called the API")

    monkeypatch.setattr(runner_module, "_request_transport", forbidden)
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(EXECUTE_LIVE=False))
    assert namespace["generations"] == [] and namespace["judge_result"] is None


def test_judge_is_separate_gated_and_immutable_in_notebook(monkeypatch, tmp_path, mocked_tutor):
    _snapshot, calls = mocked_tutor
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides())
    assert not namespace["judge_dir"].exists() and namespace["judge_result"] is None
    assert all(not url.endswith("/judge") for _method, url, _payload in calls)
    observed = []

    def fake_execute(run_dir, judge_run_id, **kwargs):
        assert kwargs["execute_live"] is True and isinstance(kwargs["budget"], Runner)
        observed.append((judge_run_id, kwargs["resume"]))
        return {"success": 0, "dispatched": 0}

    monkeypatch.setattr(judge_module, "execute_judge_run", fake_execute)
    namespace.update(EXECUTE_JUDGE_LIVE=True, JUDGE_MODEL="judge-model")
    execute_cell(namespace, "judge")
    frozen = (namespace["judge_dir"] / "manifest.json").read_bytes()
    assert namespace["judge_result"]["coverage"]["targets"] == 2
    assert set(namespace["judge_summary_df"]["criterion"]) >= {"diagnostic_question_quality", "diagnosis_match"}
    assert not (namespace["run_dir"] / "reviews" / "ratings.jsonl").exists()
    namespace["JUDGE_RESUME"] = True
    execute_cell(namespace, "judge")
    assert (namespace["judge_dir"] / "manifest.json").read_bytes() == frozen
    assert observed == [("judge-001", False), ("judge-001", True)]
    namespace["JUDGE_MODEL"] = "other-judge"
    with pytest.raises(ValueError, match="JUDGE_MODEL geaendert"):
        execute_cell(namespace, "judge")


def test_judge_requires_explicit_different_alias(monkeypatch, tmp_path, mocked_tutor):
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides())
    namespace["EXECUTE_JUDGE_LIVE"] = True
    for alias in (None, "test-model"):
        namespace["JUDGE_MODEL"] = alias
        with pytest.raises(ValueError):
            execute_cell(namespace, "judge")
    assert not namespace["judge_dir"].exists()


def test_analyze_summarizes_saved_judge_without_originals_or_network(monkeypatch, tmp_path, mocked_tutor):
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides())
    judge_module.prepare_judge_run(namespace["run_dir"], "judge-001", judge_model="judge-model")

    def forbidden(*args, **kwargs):
        pytest.fail("Analyze tried to call or prepare a live operation")

    monkeypatch.setattr(runner_module, "_request_transport", forbidden)
    monkeypatch.setattr(judge_module, "_request_transport", forbidden)
    monkeypatch.setattr(judge_module, "execute_judge_run", forbidden)
    monkeypatch.setattr(judge_module, "prepare_judge_run", forbidden)
    analyzed, _ = execute_cells(monkeypatch, tmp_path, {
        "MODE": "analyze", "RUN_ID": "live-small", "EXECUTE_LIVE": True, "EXECUTE_JUDGE_LIVE": True,
        "FETCH_SERVER_CONFIGURATION": True, "TASKS_DIR": tmp_path / "gone", "CORPUS_FILE": tmp_path / "gone.jsonl",
        "PROFILES_FILE": tmp_path / "gone-profiles.json", "EXPECTED_CONFIG_FILE": tmp_path / "gone-config.json",
    })
    assert analyzed["judge_result"]["coverage"]["targets"] == 2
    assert len(analyzed["result_df"]) == 2 and analyzed["preview_selector"]


def test_cross_run_cell_reads_other_runs_and_exports_only_here(monkeypatch, tmp_path, mocked_tutor):
    left, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(RUN_ID="reference", CONDITION_ID="fixed"))
    right, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(RUN_ID="candidate", CONDITION_ID="individual"))
    before = {str(path.relative_to(left["run_dir"])): path.read_bytes() for path in left["run_dir"].rglob("*") if path.is_file()}
    right["COMPARE_RUN_DIRS"] = [left["run_dir"]]
    execute_cell(right, "condition-comparison")
    assert right["condition_comparison"]["coverage"]["paired_responses"] == 2
    assert right["condition_comparison"]["coverage"]["pairs_missing_human_ratings"] == 2
    assert right["condition_pairs_df"]["delta"].isna().all()
    assert (right["derived_dir"] / "condition_comparisons.csv").exists()
    after = {str(path.relative_to(left["run_dir"])): path.read_bytes() for path in left["run_dir"].rglob("*") if path.is_file()}
    assert before == after


def test_notebook_jsonl_source_remains_available_without_tasks(monkeypatch, tmp_path):
    namespace, _ = execute_cells(monkeypatch, tmp_path, {
        "CASE_SOURCE": "jsonl", "TASKS_DIR": tmp_path / "missing-tasks",
        "CASE_IDS": ["chain-exp-missing-inner-001"], "PROFILE_IDS": ["base"], "HINT_LEVELS": [0, 1],
    })
    assert namespace["manifest"]["case_source"] == "jsonl"
    assert len(namespace["generations"]) == 2
    assert namespace["manifest"]["source_task_hashes"] == {}


def test_notebook_renders_untrusted_text_as_escaped_html(monkeypatch, tmp_path, mocked_tutor):
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(EXECUTE_LIVE=False))
    rendered = []
    namespace["display"] = lambda value: rendered.append(value.data)
    namespace["show_text"]('<script>alert("x")</script>')
    namespace["show_frame"](namespace["pd"].DataFrame([{"answer": '<img src=x onerror="bad()">'}]))
    assert all("<script>" not in html and "<img src=x" not in html for html in rendered)
    assert "&lt;script&gt;" in rendered[0] and "&lt;img" in rendered[1]


def test_mocked_judge_full_roundtrip_preserves_human_and_diagnostic_separation(monkeypatch, tmp_path, mocked_tutor):
    snapshot, _calls = mocked_tutor
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides())
    packet = namespace["review_rows"][0]
    submission = namespace["run_dir"] / "reviews" / "expert.csv"
    with submission.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=report_module.RFC_REVIEW_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerow({**packet, "rater_id": "expert-1", "verstaendlichkeit": "4"})
    assert report_module.import_review_ratings(namespace["run_dir"], submission)["imported"] == 1
    human_path = namespace["run_dir"] / "reviews" / "ratings.jsonl"
    before = human_path.read_bytes()
    calls = []

    def judge_transport(method, url, payload, timeout):
        calls.append((method, url, copy.deepcopy(payload)))
        if method == "GET":
            return 200, snapshot, None, ""
        judgement = {
            "ratings": {**dict.fromkeys(report_module.LIKERT_FIELDS, 4),
                        **dict.fromkeys(report_module.CHOICE_FIELDS, "nein"), "stufe_angemessen": "ja"},
            "diagnostic_question_quality": 4 if payload["stage"] == "diagnostic" else None,
            "diagnosis_match": "unklar", "justification": "", "evidence": ["Welche Regel"],
        }
        if payload["stage"] == "diagnostic":
            judgement["ratings"]["hilfreichkeit_naechster_schritt"] = None
            judgement["ratings"]["stufe_angemessen"] = "nicht_anwendbar"
        verification = {
            "mathematics_status": "unknown", "diagnosis_status": "unknown", "method": None,
            "tool_and_version": None, "evidence_refs": [], **(payload.get("verification") or {}),
        }
        body = {
            **snapshot,
            **{key: payload[key] for key in ("review_id", "target_attempt_id", "hint_sha256", "hint_level", "policy_mode", "stage")},
            "judge_model": payload["judge_model"], "execution_source": "live_judge_api",
            "reference_authority": "task_derived_hypothesis_not_authoritative", "verification": verification,
            "prompt_messages": [{"role": "system", "content": "Actual mocked judge rubric"}, {"role": "user", "content": "Quoted observed generator evidence"}],
            "judgement": judgement, "raw_response": json.dumps(judgement),
            "generation": {"requested_model": payload["judge_model"], "model_alias": payload["judge_model"],
                           "requested_temperature": 0.0, "requested_max_tokens": 1200, "json_output": True},
        }
        return 200, body, None, ""

    monkeypatch.setattr(judge_module, "_request_transport", judge_transport)
    namespace.update(EXECUTE_JUDGE_LIVE=True, JUDGE_MODEL="judge-model", JUDGE_COMPARE_HUMANS=True)
    execute_cell(namespace, "judge")
    assert len([call for call in calls if call[0] == "POST"]) == 2
    assert namespace["judge_result"]["coverage"]["successful_judgements"] == 2
    assert namespace["judge_result"]["coverage"]["human_pairs"] == 1
    diagnostic = namespace["judge_summary_df"]
    diagnostic = diagnostic[(diagnostic["criterion"] == "diagnostic_question_quality") & (diagnostic["stage"] == "diagnostic")]
    assert diagnostic.iloc[0]["median"] == 4
    assert human_path.read_bytes() == before
    assert build_report(namespace["run_dir"])["coverage"]["ratings_total"] == 1
    journal = read_jsonl(namespace["judge_dir"] / "events.jsonl")
    assert all(event["budget_cost"] == 2 for event in journal if event["event"] == "attempt_started")


def test_failed_start_keeps_dependent_turns_explicit_in_table(monkeypatch, tmp_path, mocked_tutor):
    original = runner_module._request_transport

    def transport(method, url, payload, timeout):
        if method == "POST":
            return 500, {"detail": "private upstream detail"}, None, ""
        return original(method, url, payload, timeout)

    monkeypatch.setattr(runner_module, "_request_transport", transport)
    namespace, _ = execute_cells(monkeypatch, tmp_path, small_live_overrides(
        HINT_LEVELS=[0], LEVEL_MODE="server_start", INTERACTION_SCRIPT=[{"message": "continue", "elapsed_seconds": 300}],
    ))
    assert namespace["result_df"]["outcome"].tolist() == ["server_error", "dependency_blocked"]
    assert namespace["result_df"].iloc[1]["blocked_reason"] == "predecessor_not_successful"
    assert namespace["result_df"]["hint"].eq("").all()
    assert namespace["review_rows"] == []


def test_full_notebook_server_start_demo_stays_offline_and_unexecuted(monkeypatch, tmp_path):
    def forbidden(*args):
        pytest.fail("Demo called the server")

    monkeypatch.setattr(runner_module, "_request_transport", forbidden)
    namespace, _ = execute_cells(monkeypatch, tmp_path, {
        "LEVEL_MODE": "server_start", "HINT_LEVELS": [0], "FETCH_SERVER_CONFIGURATION": True,
        "INTERACTION_SCRIPT": [{"message": "continue", "elapsed_seconds": 120}],
    })
    assert len(namespace["plan_jobs"]) == 24
    assert namespace["result_df"]["outcome"].eq("not_executed").all()
    assert namespace["result_df"]["effective_hint_level"].isna().all()
    assert namespace["report_result"]["coverage"]["responses_total"] == 0


def test_real_nbclient_run_all_from_notebook_directory_is_offline(tmp_path):
    nbclient = pytest.importorskip("nbclient")
    nbformat = pytest.importorskip("nbformat")
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    configuration = next(cell for cell in notebook["cells"] if cell["id"] == "configuration")
    configuration["source"] += (
        "\nRUN_ROOT = Path(" + repr(str(tmp_path)) + ")\nrun_dir = RUN_ROOT / RUN_ID\n"
        "import requests\n"
        "def forbidden_network(*args, **kwargs):\n    raise AssertionError('Default Run All attempted networking')\n"
        "requests.sessions.Session.request = forbidden_network\n"
    )
    nbclient.NotebookClient(notebook, timeout=120, kernel_name="python3",
                            resources={"metadata": {"path": str(NOTEBOOK_PATH.parent)}}).execute()
    records = read_jsonl(tmp_path / "testbench-demo-001" / "generations.jsonl")
    assert len(records) == 24 and all(record["execution_source"] == "offline_demo" for record in records)
    assert (tmp_path / "testbench-demo-001" / "derived" / "automatic_checks.png").is_file()
    checked_in = nbformat.read(NOTEBOOK_PATH, as_version=4)
    assert all(cell["outputs"] == [] and cell["execution_count"] is None for cell in checked_in["cells"] if cell["cell_type"] == "code")
