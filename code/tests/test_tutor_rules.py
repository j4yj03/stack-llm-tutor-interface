"""Actual API roundtrips for stage 0, start selection and next-turn adaptation."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.database import initialize_database
from app.llm import LLMError
from app.runtime_config import configuration_hash, public_configuration
from app.schemas import ContextOptions, StackContext
from evaluation.checks import run_checks_for_run
from evaluation.corpus import load_experiment, load_profiles, validate_experiment
from evaluation.models import PROFILE_FLAG_NAMES
from evaluation.notebook import prepare_run, read_jsonl
from evaluation.runner import Runner
from evaluation.task_cases import cases_from_tasks

CODE_DIR = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self):
        self.calls = []
        self.answers = []

    def chat(self, messages, **parameters):
        self.calls.append({"messages": messages, **parameters})
        answer = self.answers.pop(0) if self.answers else "Welche Regel hast du bisher verwendet?"
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def api(monkeypatch, chat_store):
    fake = FakeClient()
    monkeypatch.setattr(main, "CHAT_STORE", chat_store)
    monkeypatch.setattr(main, "initialize_database", lambda: initialize_database(chat_store.database_path))
    monkeypatch.setattr(main, "create_llm_client", lambda: fake)
    monkeypatch.setattr(config, "TUTOR_START_MODE", "fixed")
    monkeypatch.setattr(config, "TUTOR_RESPONSE_FORMAT", "text")
    monkeypatch.setattr(config, "TUTOR_ADAPTIVE_ENABLED", False)
    monkeypatch.setattr(config, "EVALUATION_API_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_API_TOKEN", "test-evaluation-token")
    with TestClient(main.app) as client:
        yield client, fake, chat_store


def payload(level=0):
    case = cases_from_tasks(CODE_DIR / "tasks")[0]
    return {"stack": {**case.tutor_context.model_dump(), "diagnosis_source": "synthetic"},
            "hint_level": level, "context_options": {name: name in {"include_question_text", "include_student_answer"}
                                                       for name in PROFILE_FLAG_NAMES}}


def test_stage_zero_and_configured_generation_are_observed(api, monkeypatch):
    client, fake, store = api
    monkeypatch.setattr(config, "LLM_TEMPERATURE", 0.7)
    monkeypatch.setattr(config, "LLM_MAX_TOKENS", 720)
    result = client.post("/api/tutor/start", json=payload()).json()
    assert result["hint_level"] == result["baseline_hint_level"] == 0
    assert result["stage"] == "diagnostic"
    assert result["llm_operations"] == 1
    assert fake.calls[0]["temperature"] == 0.7
    assert fake.calls[0]["max_tokens"] == 720
    assert result["config_sha256"] == configuration_hash(result["configuration"])
    assert store.get_chat(result["chat_id"])["baseline_hint_level"] == 0


def test_individual_start_uses_only_requested_stage_zero_context(api, monkeypatch):
    client, fake, _store = api
    monkeypatch.setattr(config, "TUTOR_START_MODE", "individual")
    fake.answers = [json.dumps({"hint_level": 2, "reason": "Unsichere Einschaetzung"}), "Welche Regel brauchst du?"]
    body = payload(None)
    body["stack"]["learning_goals"] = ["HIDDEN_GOAL_MARKER"]
    response = client.post("/api/tutor/start", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["baseline_hint_level"] == result["hint_level"] == 2
    assert result["llm_operations"] == 2
    assert "HIDDEN_GOAL_MARKER" not in json.dumps(fake.calls[0]["messages"])
    assert result["start_decision"]["source"] == "model_hypothesis"
    assert result["start_prompt_messages"] == fake.calls[0]["messages"]


def test_invalid_individual_choice_fails_without_fallback(api, monkeypatch):
    client, fake, store = api
    monkeypatch.setattr(config, "TUTOR_START_MODE", "individual")
    fake.answers = ['{"hint_level":99,"reason":"invalid"}']
    response = client.post("/api/tutor/start", json=payload(None))
    assert response.status_code == 502
    assert len(fake.calls) == 1


@pytest.mark.parametrize("elapsed, confused, expected", [(200, False, 0), (1, True, 0), (200, True, 1)])
def test_adaptive_level_requires_time_and_corroborating_signal(api, monkeypatch, elapsed, confused, expected):
    client, fake, _store = api
    monkeypatch.setattr(config, "TUTOR_ADAPTIVE_ENABLED", True)
    initial = client.post("/api/tutor/start", json=payload()).json()
    assert len(fake.calls) == 1
    response = client.post(f"/api/tutor/{initial['chat_id']}/message",
                           json={"message": "Ich verstehe nicht.", "simulation_elapsed_seconds": elapsed,
                                 "confusion_signal": confused},
                           headers={"X-Evaluation-Token": "test-evaluation-token"})
    assert response.status_code == 200
    result = response.json()
    assert result["hint_level"] == expected
    assert result["baseline_hint_level"] == 0
    assert result["adaptation"]["time_source"] == "simulated"
    assert len(fake.calls) == 2  # No selection or timer operation.


def test_simulated_followup_requires_auth_before_storing_message(api):
    client, fake, store = api
    initial = client.post("/api/tutor/start", json=payload()).json()
    before = store.get_messages(initial["chat_id"])
    response = client.post(f"/api/tutor/{initial['chat_id']}/message",
                           json={"message": "Ich verstehe nicht.", "simulation_elapsed_seconds": 200})
    assert response.status_code == 401
    assert store.get_messages(initial["chat_id"]) == before
    assert len(fake.calls) == 1


def test_stage_zero_history_cap_does_not_drop_current_message(api, monkeypatch):
    client, fake, _store = api
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", {**config.TUTOR_STAGE0_CONTEXT_OPTIONS, "chat_history": False})
    body = payload()
    body["context_options"]["include_chat_history"] = True
    initial = client.post("/api/tutor/start", json=body).json()
    response = client.post(f"/api/tutor/{initial['chat_id']}/message",
                           json={"message": "CURRENT_MESSAGE_MARKER", "context_options": body["context_options"]})
    assert response.status_code == 200
    assert response.json()["context_options"]["include_chat_history"] is False
    assert "CURRENT_MESSAGE_MARKER" in fake.calls[-1]["messages"][-1]["content"]


def test_failed_adaptive_generation_does_not_commit_level(api, monkeypatch):
    client, fake, store = api
    monkeypatch.setattr(config, "TUTOR_ADAPTIVE_ENABLED", True)
    initial = client.post("/api/tutor/start", json=payload()).json()
    fake.answers = [LLMError("private cause")]
    response = client.post(f"/api/tutor/{initial['chat_id']}/message",
                           json={"message": "Ich verstehe nicht.", "simulation_elapsed_seconds": 200,
                                 "confusion_signal": True}, headers={"X-Evaluation-Token": "test-evaluation-token"})
    assert response.status_code == 502
    assert store.get_chat(initial["chat_id"])["current_hint_level"] == 0
    assert store.get_chat(initial["chat_id"])["baseline_hint_level"] == 0


def test_normal_followup_after_simulation_is_not_labelled_simulated(api):
    client, _fake, _store = api
    initial = client.post("/api/tutor/start", json=payload()).json()
    client.post(f"/api/tutor/{initial['chat_id']}/message", json={"message": "Frage", "simulation_elapsed_seconds": 200},
                headers={"X-Evaluation-Token": "test-evaluation-token"})
    normal = client.post(f"/api/tutor/{initial['chat_id']}/message", json={"message": "Neue Frage"}).json()
    assert normal["adaptation"]["time_source"] == "observed_server_interval"
    assert normal["adaptation"]["elapsed_seconds"] < 200


def test_elapsed_time_is_unknown_after_worker_change(api, monkeypatch):
    client, _fake, _store = api
    initial = client.post("/api/tutor/start", json=payload()).json()
    monkeypatch.setattr(config, "TUTOR_ADAPTIVE_ENABLED", True)
    monkeypatch.setattr(main, "SESSION_CLOCK_ID", "other-worker")
    result = client.post(f"/api/tutor/{initial['chat_id']}/message", json={"message": "Ich verstehe nicht."}).json()
    assert result["hint_level"] == 0
    assert result["adaptation"]["elapsed_seconds"] is None
    assert result["adaptation"]["reason"] == "time_unknown"


def test_structured_hypothesis_is_separate_and_bounded(api, monkeypatch):
    client, fake, _store = api
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "model")
    monkeypatch.setattr(config, "TUTOR_RESPONSE_FORMAT", "structured")
    fake.answers = [json.dumps({"hint": "Welche Faktoren erkennst du?", "diagnosis_hypothesis": "Vermutlich fehlt ein Faktor."})]
    result = client.post("/api/tutor/start", json=payload(1)).json()
    assert result["hint"] == "Welche Faktoren erkennst du?"
    assert result["diagnosis_hypothesis"] == "Vermutlich fehlt ein Faktor."
    fake.answers = [json.dumps({"hint": "Frage", "diagnosis_hypothesis": "x" * 2001})]
    assert client.post("/api/tutor/start", json=payload(1)).status_code == 502


def test_config_endpoint_observes_the_same_active_policy_as_generation(api, monkeypatch):
    client, _fake, _store = api
    monkeypatch.setenv("TUTOR_LEVEL_1_MAX_WORDS", "9")
    response = client.get("/api/evaluation/config", headers={"X-Evaluation-Token": "test-evaluation-token"})
    assert response.status_code == 200
    assert response.json()["configuration"]["hint_policy"] == main.HINT_POLICY.levels
    assert response.json()["config_sha256"] == client.get("/health").json()["config_sha256"]


def test_existing_database_is_migrated_without_dropping_records(tmp_path):
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE chats(chat_id TEXT PRIMARY KEY, question_id TEXT NOT NULL, stack_context_json TEXT NOT NULL, current_hint_level INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    connection.execute("INSERT INTO chats VALUES ('old','task','{}',2,'before','before')")
    connection.commit()
    connection.close()
    initialize_database(path)
    initialize_database(path)
    connection = sqlite3.connect(path)
    row = connection.execute("SELECT baseline_hint_level,session_state_json,created_at FROM chats WHERE chat_id='old'").fetchone()
    connection.close()
    assert row == (2, "{}", "before")


def test_partially_migrated_baseline_is_repaired(tmp_path):
    path = tmp_path / "partial.db"
    initialize_database(path)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO chats(chat_id,question_id,stack_context_json,current_hint_level,created_at,updated_at,baseline_hint_level) VALUES ('old','task','{}',3,'before','before',NULL)")
    connection.commit()
    connection.close()
    initialize_database(path)
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT baseline_hint_level FROM chats").fetchone()[0] == 3
    connection.close()


def test_reduced_maximum_rejects_old_chat_without_lowering_it(api, monkeypatch):
    client, fake, store = api
    initial = client.post("/api/tutor/start", json=payload(4)).json()
    monkeypatch.setattr(main, "MAX_HINT_LEVEL", 2)
    before = store.get_messages(initial["chat_id"])
    assert client.post(f"/api/tutor/{initial['chat_id']}/next-hint", json={}).status_code == 409
    assert client.post(f"/api/tutor/{initial['chat_id']}/message", json={"message": "Frage"}).status_code == 409
    assert store.get_chat(initial["chat_id"])["current_hint_level"] == 4
    assert store.get_messages(initial["chat_id"]) == before
    assert len(fake.calls) == 1


@pytest.mark.parametrize("structured", [False, True])
def test_invalid_unicode_provider_text_fails_before_level_commit(api, monkeypatch, structured):
    client, fake, store = api
    initial = client.post("/api/tutor/start", json=payload(1)).json()
    if structured:
        monkeypatch.setattr(config, "TUTOR_RESPONSE_FORMAT", "structured")
        fake.answers = [json.dumps({"hint": "\ud800", "diagnosis_hypothesis": None})]
    else:
        fake.answers = ["\ud800"]
    response = client.post(f"/api/tutor/{initial['chat_id']}/next-hint", json={})
    assert response.status_code == 502
    assert store.get_chat(initial["chat_id"])["current_hint_level"] == 1
    assert len(store.get_messages(initial["chat_id"])) == 1


def test_task_condition_and_script_roundtrip_through_actual_api(api, monkeypatch, tmp_path):
    client, fake, _store = api
    monkeypatch.setattr(config, "TUTOR_ADAPTIVE_ENABLED", True)
    monkeypatch.setattr(config, "DEFAULT_HINT_LEVEL", 0)
    flags = {name: name in {"include_question_text", "include_student_answer", "include_chat_history"}
             for name in PROFILE_FLAG_NAMES}
    options = {
        "run_dir": tmp_path / "roundtrip", "corpus_path": None, "profiles_path": CODE_DIR / "evaluation/data/context_profiles.json",
        "tasks_dir": CODE_DIR / "tasks", "case_ids": ["task-prod-missing-term-001"], "profile_ids": ["custom"],
        "custom_flags": flags, "hint_levels": [0], "level_mode": "server_start", "model": config.LLM_MODEL,
        "mode": "live", "base_url": "http://testserver", "allow_task_derived_cases": True,
        "interaction_script": [{"message": "Ich verstehe nicht.", "elapsed_seconds": 200, "confusion_signal": True}],
    }
    prepare_run(**options)
    def transport(method, url, body, timeout):
        response = client.request(method, url, json=body if method == "POST" else None,
                                  headers={"X-Evaluation-Token": "test-evaluation-token"})
        return response.status_code, response.json(), None, ""
    stats = Runner(options["run_dir"], transport=transport).run(execute_live=True)
    assert stats["success"] == 2
    records = read_jsonl(options["run_dir"] / "generations.jsonl")
    assert [record["returned"]["hint_level"] for record in records] == [0, 1]
    assert records[1]["returned"]["baseline_hint_level"] == 0
    run_checks_for_run(options["run_dir"])
    assert not [check for check in read_jsonl(options["run_dir"] / "checks.jsonl")
                if check["check_id"] in {"response_identity", "context_options_match", "prompt_required_content"}
                and check["status"] == "fail"]


def test_cli_task_case_payload_is_valid_for_actual_api(api):
    from evaluation.corpus import build_request_payload
    client, _fake, _store = api
    case = cases_from_tasks(CODE_DIR / "tasks")[0]
    profile = load_profiles(CODE_DIR / "evaluation/data/context_profiles.json").by_id()["diagnosis_feedback"]
    response = client.post("/api/tutor/start", json=build_request_payload(case, profile, 1, config.LLM_MODEL))
    assert response.status_code == 200


@pytest.mark.parametrize("name", ["rule_comparison", "start_comparison", "adaptation_comparison"])
def test_protocol_two_presets_are_offline_valid_and_preserve_hypotheses(name):
    cases = cases_from_tasks(CODE_DIR / "tasks")
    profiles = load_profiles(CODE_DIR / "evaluation/data/context_profiles.json")
    experiment = load_experiment(CODE_DIR / "evaluation/experiments" / (name + ".json"))
    assert experiment.protocol_version == "eval-protocol-2"
    assert validate_experiment(experiment, cases, profiles) == []
    assert experiment.allow_unverified_cases and experiment.allow_task_derived_cases
    assert all(case.evaluation_only.verification.mathematics_status == "pending" for case in cases)


def test_optional_judge_roundtrip_does_not_enter_human_metrics(api, monkeypatch, tmp_path):
    import app.evaluation_api as evaluation_api
    from evaluation.judge import execute_judge_run, prepare_judge_run, summarize_judgements
    from evaluation.report import CHOICE_FIELDS, LIKERT_FIELDS, build_report

    client, _fake, _store = api
    monkeypatch.setattr(config, "EVALUATION_JUDGE_MODEL", "judge-test")
    monkeypatch.setattr(config, "ALLOWED_MODELS", {*config.ALLOWED_MODELS, "judge-test"})
    judgement = {"ratings": {**{name: 4 for name in LIKERT_FIELDS},
                              **{name: "unklar" for name in CHOICE_FIELDS}},
                 "diagnostic_question_quality": None, "diagnosis_match": "unklar",
                 "justification": "Hypothesenvergleich, keine Verifizierung.", "evidence": []}
    fake_judge = FakeClient()
    fake_judge.answers = [json.dumps(judgement)]
    monkeypatch.setattr(evaluation_api, "create_llm_client", lambda: fake_judge)
    run_dir = tmp_path / "generator-and-judge"
    flags = {name: name in {"include_question_text", "include_student_answer"} for name in PROFILE_FLAG_NAMES}
    prepare_run(run_dir, None, CODE_DIR / "evaluation/data/context_profiles.json",
                ["task-prod-missing-term-001"], ["custom"], flags, [1], config.LLM_MODEL,
                "live", "http://testserver", tasks_dir=CODE_DIR / "tasks", allow_task_derived_cases=True)
    def transport(method, url, body, timeout):
        response = client.request(method, url, json=body if method == "POST" else None,
                                  headers={"X-Evaluation-Token": "test-evaluation-token"})
        return response.status_code, response.json(), None, ""
    assert Runner(run_dir, transport=transport).run(execute_live=True)["success"] == 1
    prepare_judge_run(run_dir, "judge-roundtrip", judge_model="judge-test")
    stats = execute_judge_run(run_dir, "judge-roundtrip", execute_live=True, transport=transport,
                              budget=Runner(run_dir, transport=transport))
    assert stats["success"] == 1
    assert len(fake_judge.calls) == 1
    assert summarize_judgements(run_dir, "judge-roundtrip")["coverage"]["successful_judgements"] == 1
    assert build_report(run_dir)["coverage"]["ratings_total"] == 0
    assert not (run_dir / "reviews" / "ratings.jsonl").exists()
