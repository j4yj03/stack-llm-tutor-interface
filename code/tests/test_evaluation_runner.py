"""Tests für Budget, Journal, Resume und Fehlerklassifikation (gemockt)."""

import json
from pathlib import Path

import pytest

from evaluation.corpus import load_cases, load_experiment, load_profiles
from evaluation.runner import (
    CODE_DIR,
    Runner,
    RunnerError,
    create_run,
    load_plan,
    load_manifest,
    _classify,
)

EVAL_DIR = CODE_DIR / "evaluation"
DATA_DIR = EVAL_DIR / "data"


def make_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "eval-001"
    experiment_path = EVAL_DIR / "experiments" / "pilot.json"
    # Nur 2 Jobs für schnelle Tests: kleines legales Experiment anlegen.
    experiment = json.loads(
        experiment_path.read_text(encoding="utf-8")
    )
    experiment["profiles"] = ["base"]
    experiment["hint_levels"] = [1]
    experiment["repetitions"] = 1
    experiment["control_jobs"] = []
    experiment_path_small = tmp_path / "exp_small.json"
    experiment_path_small.write_text(
        json.dumps(experiment, ensure_ascii=False), encoding="utf-8"
    )
    create_run(
        run_dir=run_dir,
        experiment_path=experiment_path_small,
        corpus_path=DATA_DIR / "example_cases.jsonl",
        profiles_path=DATA_DIR / "context_profiles.json",
        base_url="http://tutor.test",
    )
    return run_dir


def fake_transport_factory(status=200, body=None, error=None):
    calls = []

    def transport(method, url, payload, timeout):
        if method == "GET":
            return 200, {"tasks_loaded": 2, "default_model": "x"}, None, ""
        calls.append(payload)
        if error is not None:
            return None, None, error, "verbindung fehlgeschlagen"
        return status, body, None, ""

    transport.calls = calls
    return transport


def success_body(index=0):
    payload_hint = "Hinweis " + str(index)
    return {
        "chat_id": "11111111-1111-4111-8111-111111111111",
        "question_id": "ableitung_kettenregel_exp_001",
        "hint_level": 1,
        "model": "server-model",
        "hint": payload_hint,
        "history": [],
        "prompt_messages": [
            {"role": "system", "content": "policy"},
            {"role": "user", "content": "context"},
        ],
        "context_options": {"include_question_text": True},
    }


class ManualClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_run_without_live_gate_does_not_call_network(tmp_path):
    run_dir = make_run_dir(tmp_path)
    transport = fake_transport_factory(body=success_body())
    runner = Runner(run_dir=run_dir, transport=transport,
                    sleep=ManualClock().sleep, clock=ManualClock().clock)
    with pytest.raises(RunnerError):
        runner.run(execute_live=False)
    assert transport.calls == []


def test_run_executes_jobs_and_records_payload(tmp_path):
    run_dir = make_run_dir(tmp_path)
    transport = fake_transport_factory(body=success_body())
    clock = ManualClock()
    runner = Runner(run_dir=run_dir, transport=transport,
                    sleep=clock.sleep, clock=clock.clock)
    stats = runner.run(execute_live=True)
    assert stats["dispatched"] == stats["planned"]
    assert stats["success"] == stats["planned"]
    assert len(transport.calls) == stats["planned"]
    records = [
        json.loads(line)
        for line in (run_dir / "generations.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    payload = records[0]["request_payload"]
    assert payload["chat_id"] is None
    assert len(payload["context_options"]) == 10
    assert records[0]["request_sha256"]
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    # Journal vor dem Versand: start + finish je Versuch.
    assert events.count("attempt_started") == stats["dispatched"]
    assert events.count("attempt_finished") == stats["dispatched"]


def test_failure_statuses_are_classified_without_retry(tmp_path):
    run_dir = make_run_dir(tmp_path)
    transport = fake_transport_factory(status=502, body={"detail": "Fehler"})
    runner = Runner(run_dir=run_dir, transport=transport,
                    sleep=ManualClock().sleep, clock=ManualClock().clock)
    stats = runner.run(execute_live=True)
    assert stats["dispatched"] >= 1
    assert stats["server_error"] >= 1
    assert stats["success"] == 0
    # Keine stillen Retries: ein Versuch je geplantem Job.
    assert transport.calls.__len__() == stats["planned"]


def test_transport_ambiguity_is_kept_unclassified(tmp_path):
    run_dir = make_run_dir(tmp_path)
    transport = fake_transport_factory(error="timeout")
    runner = Runner(run_dir=run_dir, transport=transport,
                    sleep=ManualClock().sleep, clock=ManualClock().clock)
    stats = runner.run(execute_live=True)
    assert stats["transport_ambiguous"] == stats["planned"]
    records = [
        json.loads(line)
        for line in (run_dir / "generations.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert all(record["outcome"] == "transport_ambiguous" for record in records)


def test_budget_paces_before_dispatch(tmp_path):
    run_dir = make_run_dir(tmp_path)
    transport = fake_transport_factory(body=success_body())
    clock = ManualClock()
    runner = Runner(run_dir=run_dir, transport=transport,
                    sleep=clock.sleep, clock=clock.clock)
    manifest = load_manifest(run_dir)
    # Limit drosseln: 2 Jobs, Grenze 1/h → 2. Versuch muss warten.
    manifest["max_generations_per_hour"] = 1
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    jobs = load_plan(run_dir)
    assert len(jobs) >= 2
    runner.run(execute_live=True)
    # Mindestens eine Budget-Warteperiode mit positiver Dauer.
    assert any(wait > 0 for wait in clock.sleeps)


def test_resume_retries_nothing_and_verifies_identity(tmp_path):
    run_dir = make_run_dir(tmp_path)
    # Erster Lauf: alle Jobs fehlschlagen (500).
    failing = fake_transport_factory(status=500, body={"detail": "x"})
    Runner(run_dir=run_dir, transport=failing,
           sleep=ManualClock().sleep, clock=ManualClock().clock
           ).run(execute_live=True)
    first_calls = len(failing.calls)
    # Resume ohne --retry-failed: nichts wird erneut gesendet.
    resumed = fake_transport_factory(body=success_body())
    stats = Runner(run_dir=run_dir, transport=resumed,
                   sleep=ManualClock().sleep, clock=ManualClock().clock
                   ).run(execute_live=True, resume=True)
    assert stats["dispatched"] == 0
    assert len(resumed.calls) == 0
    assert len(failing.calls) == first_calls
    # --retry-failed: explizite manuelle Wiederholung als neuer Versuch.
    stats_retry = Runner(run_dir=run_dir, transport=resumed,
                         sleep=ManualClock().sleep, clock=ManualClock().clock
                         ).run(execute_live=True, resume=True, retry_failed=True)
    assert stats_retry["dispatched"] == stats_retry["planned"]
    assert stats_retry["success"] == stats_retry["planned"]
    # Erfolg eines Jobs überschreibt Fehlerklassifikation (best outcome).
    generations = [
        json.loads(line)
        for line in (run_dir / "generations.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    by_job = {}
    for record in generations:
        by_job[record["job_id"]] = by_job.get(record["job_id"], []) + [record]
    assert any(
        len(attempts) >= 2 and attempts[-1]["outcome"] == "success"
        for attempts in by_job.values()
    )


def test_resume_aborts_on_changed_corpus(tmp_path):
    run_dir = make_run_dir(tmp_path)
    Runner(run_dir=run_dir, transport=fake_transport_factory(body=success_body()),
           sleep=ManualClock().sleep, clock=ManualClock().clock
           ).run(execute_live=True)
    corpus_path = DATA_DIR / "example_cases.jsonl"
    original = corpus_path.read_text(encoding="utf-8")
    try:
        corpus_path.write_text(original + "\n", encoding="utf-8")
        with pytest.raises(RunnerError):
            Runner(run_dir=run_dir,
                   transport=fake_transport_factory(body=success_body()),
                   sleep=ManualClock().sleep, clock=ManualClock().clock
                   ).run(execute_live=True, resume=True)
    finally:
        corpus_path.write_text(original, encoding="utf-8")


def test_in_flight_attempt_is_marked_ambiguous_on_resume(tmp_path):
    run_dir = make_run_dir(tmp_path)
    jobs = load_plan(run_dir)
    # Simulation: Prozess starb nach dem Journal, vor der Ergebniszeile.
    target = jobs[0]
    (run_dir / "events.jsonl").write_text(
        json.dumps({
            "event": "attempt_started",
            "attempt_id": "attempt-deadbean",
            "job_id": target["job_id"],
            "execution_source": "live_tutor_api",
            "case_id": target["case_id"],
            "profile_id": target["profile_id"],
            "hint_level": target["hint_level"],
            "requested_model": None,
            "repetition": 1,
            "request_sha256": target["request_sha256"],
            "ts_utc": "2026-09-20T10:00:00+00:00",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    transport = fake_transport_factory(body=success_body())
    stats = Runner(run_dir=run_dir, transport=transport,
                   sleep=ManualClock().sleep, clock=ManualClock().clock
                   ).run(execute_live=True, resume=True)
    # Der unklare Versuch wird nicht wiederholt.
    assert stats["dispatched"] == len(jobs) - 1
    assert stats["in_flight_repaired"] == 1
    generations = [
        json.loads(line)
        for line in (run_dir / "generations.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    repaired = [record for record in generations
                if record["attempt_id"] == "attempt-deadbean"]
    assert repaired and repaired[0]["outcome"] == "transport_ambiguous"


def test_classify_mapping():
    assert _classify(200, None) == "success"
    assert _classify(429, None) == "rate_limited"
    assert _classify(400, None) == "http_error"
    assert _classify(502, None) == "server_error"
    assert _classify(None, "timeout") == "transport_ambiguous"
    assert _classify(None, "connection") == "transport_ambiguous"
    assert _classify(None, "request") == "transport_error"
