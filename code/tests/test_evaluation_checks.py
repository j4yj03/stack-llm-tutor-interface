"""Tests der automatischen Prüfungen (checks.py) — offline.

Verwendet den echten Fallbestand und die echte Stufen-Policy; sympy
ist optional, die Tests tolerant.
"""

import json
from pathlib import Path

import pytest

from evaluation.checks import (
    load_policy,
    normalize_expression,
    run_checks,
    symbolic_equivalence,
)
from evaluation.corpus import (
    build_request_payload,
    load_cases,
    load_profiles,
)

CODE_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = CODE_DIR / "evaluation"
POLICY_PATH = CODE_DIR / "config" / "hint_levels.json"

POLICY = load_policy(POLICY_PATH)
CASES = {case.case_id: case for case in
         load_cases(EVAL_DIR / "data" / "example_cases.jsonl")}
PROFILES = {profile.profile_id: profile for profile in
            load_profiles(EVAL_DIR / "data" / "context_profiles.json").profiles}
CASE = CASES["chain-exp-missing-inner-001"]
FINAL = CASE.evaluation_only.reference.final_answer


def make_generation(hint, level=3, include_final=False, checked_final=None,
                    model="test-model", missing_prompt_part=None):
    profile = PROFILES["steps"]
    payload = build_request_payload(CASE, profile, level, model)
    prompt = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": (
            CASE.tutor_context.question_text + " "
            + CASE.tutor_context.student_answer
        )},
    ]
    if missing_prompt_part is None:
        user_chunks = [
            CASE.tutor_context.question_text,
            CASE.tutor_context.student_answer,
            CASE.tutor_context.diagnosis_code,
            CASE.tutor_context.prt_feedback,
            CASE.tutor_context.learning_goals[0],
            CASE.tutor_context.math_rules[0],
            CASE.evaluation_only.reference.solution_steps[0],
        ]
        prompt[1]["content"] = " ".join(user_chunks)
    return {
        "attempt_id": "attempt-test",
        "job_id": "job-test",
        "outcome": "success",
        "case_id": CASE.case_id,
        "profile_id": "steps",
        "hint_level": level,
        "request_payload": payload,
        "returned": {
            "question_id": payload["stack"]["question_id"],
            "hint_level": level,
            "model": model,
            "hint": hint,
            "prompt_messages": prompt,
            "context_options": payload["context_options"],
        },
    }


def check_by_id(records, check_id):
    return next(record for record in records if record["check_id"] == check_id)


def test_word_count_and_level_mention():
    records = run_checks(
        make_generation("Schau dir zuerst die innere Funktion an. Was wäre ihr Ableitung?"),
        CASE, PROFILES["steps"], POLICY
    )
    assert check_by_id(records, "word_count")["status"] == "pass"
    assert check_by_id(records, "hint_level_mention")["status"] == "pass"

    long_hint = "Wort " * 400
    records = run_checks(make_generation(long_hint), CASE, PROFILES["steps"], POLICY)
    assert check_by_id(records, "word_count")["status"] == "fail"

    records = run_checks(
        make_generation("Das ist Hilfestufe 3. Prüfe die innere Ableitung."),
        CASE, PROFILES["steps"], POLICY
    )
    assert check_by_id(records, "hint_level_mention")["status"] == "fail"


def test_prompt_required_and_guard_checks():
    # Vollständiger Kontext im Prompt → pass.
    records = run_checks(
        make_generation("Ein allgemeiner Hinweis ohne die Endlösung."),
        CASE, PROFILES["steps"], POLICY
    )
    assert check_by_id(records, "prompt_required_content")["status"] == "pass"
    # Stufe 3 sperrt die Endlösung (Steps-Profil sendet die Guard-Endlösung
    # für den serverseitigen Literal-Schutz, include_final_answer bleibt false).
    guard = check_by_id(records, "prompt_solution_guard")
    assert guard["status"] == "pass"

    # Endlösung im Prompt trotz Sperre → fail.
    generation = make_generation("Ein Hinweis.")
    generation["returned"]["prompt_messages"][1]["content"] += " " + FINAL
    records = run_checks(generation, CASE, PROFILES["steps"], POLICY)
    guard = check_by_id(records, "prompt_solution_guard")
    assert guard["status"] == "fail"
    assert "final_answer" in guard["evidence"]["leaked"]


def test_disclosure_literal_and_level4_semantics():
    # Unzulässige Offenlegung auf Stufe 3.
    generation = make_generation(
        "Die Ableitung ist " + FINAL + ".", level=3
    )
    records = run_checks(generation, CASE, PROFILES["steps"], POLICY)
    disclosure = check_by_id(records, "final_answer_disclosure")
    assert disclosure["status"] == "fail"
    assert disclosure["evidence"]["present"] is True
    assert disclosure["evidence"]["allowed_at_level"] is False

    # Gleicher Treffer auf Stufe 4: erlaubt, kein Regelverstoß.
    generation = make_generation(
        "Ausführliche Erklärung … " + FINAL, level=4
    )
    records = run_checks(generation, CASE, PROFILES["steps"], POLICY)
    disclosure = check_by_id(records, "final_answer_disclosure")
    assert disclosure["status"] == "pass"
    assert disclosure["evidence"]["allowed_at_level"] is True


def test_disclosure_detects_equivalent_form():
    equivalent = CASE.evaluation_only.reference.equivalent_forms[1]
    generation = make_generation("Ergebnis: " + equivalent, level=3)
    records = run_checks(generation, CASE, PROFILES["steps"], POLICY)
    disclosure = check_by_id(records, "final_answer_disclosure")
    assert disclosure["status"] == "fail"
    assert disclosure["evidence"]["match_kind"] == "literal_or_equivalent"


def test_symbolic_equivalence_boundary_behaviour():
    equivalent, status = symbolic_equivalence("2+2", "4")
    if status.startswith("sympy nicht verfügbar"):
        assert equivalent is None
    else:
        assert equivalent is True
        # äquivalente Umformung
        ok, _ = symbolic_equivalence("exp(x)*2", "2*exp(x)")
        assert ok is True
    # Nicht ausführbarer Text → ausdrücklich unbestimmt, nicht falsch.
    equivalent, status = symbolic_equivalence(
        "die innere Ableitung", FINAL
    )
    assert equivalent is None
    # Sicherheitsgrenzen.
    equivalent, status = symbolic_equivalence("__import__('os')", FINAL)
    assert equivalent is None


def test_failed_generation_is_not_checkable():
    records = run_checks(
        {"outcome": "server_error", "hint_level": 3},
        CASE, PROFILES["steps"], POLICY
    )
    assert len(records) == 1
    assert records[0]["check_id"] == "response_available"
    assert records[0]["status"] == "not_applicable"


def test_run_checks_for_run_writes_checks_file(tmp_path: Path):
    from evaluation.checks import run_checks_for_run
    from evaluation.corpus import load_experiment
    from evaluation.runner import create_run

    experiment = load_experiment(
        EVAL_DIR / "experiments" / "pilot.json"
    ).model_copy(deep=True)
    experiment.profiles = ["base"]
    experiment.hint_levels = [1]
    experiment.repetitions = 1
    experiment.control_jobs = []
    experiment_path = tmp_path / "exp.json"
    experiment_path.write_text(
        experiment.model_dump_json(), encoding="utf-8"
    )
    run_dir = tmp_path / "runs" / "checks-e2e"
    create_run(
        run_dir=run_dir,
        experiment_path=experiment_path,
        corpus_path=EVAL_DIR / "data" / "example_cases.jsonl",
        profiles_path=EVAL_DIR / "data" / "context_profiles.json",
        base_url="http://tutor.test",
    )

    from evaluation.corpus import build_request_payload

    case = CASES["chain-exp-missing-inner-001"]
    profile = PROFILES["base"]
    payload = build_request_payload(case, profile, 1, None)
    user_content = (
        case.tutor_context.question_text + " "
        + case.tutor_context.student_answer
    )

    def generation(id_suffix, *, options=None, hint=None):
        record = {
            "schema_version": "1.0",
            "run_id": "checks-e2e",
            "attempt_id": "attempt-" + id_suffix,
            "job_id": "job-" + id_suffix,
            "execution_source": "live_tutor_api",
            "case_id": case.case_id,
            "task_instance_id": case.case_id,
            "profile_id": "base",
            "hint_level": 1,
            "requested_model": None,
            "repetition": 1,
            "request_payload": payload,
            "request_sha256": "0" * 64,
            "started_at_utc": "2026-09-21T10:00:00+00:00",
            "finished_at_utc": "2026-09-21T10:00:01+00:00",
            "duration_ms": 100,
            "outcome": "success",
            "returned": {
                "question_id": payload["stack"]["question_id"],
                "hint_level": 1,
                "model": "server-model",
                "hint": hint or (
                    "Prüfe zuerst die innere Funktion der Verkettung."
                ),
                "prompt_messages": [
                    {"role": "system", "content": "policy"},
                    {"role": "user", "content": user_content},
                ],
                "context_options": options or payload["context_options"],
            },
            "safe_error": None,
            "retry_of_attempt_id": None,
        }
        return record

    generations_path = run_dir / "generations.jsonl"
    with open(generations_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(generation("0001"), ensure_ascii=False) + "\n")
        # Manipulierter Datensatz: abweichende Optionen → muss failen.
        mismatch = generation(
            "0002",
            options={**payload["context_options"], "include_diagnosis_code": True},
        )
        handle.write(json.dumps(mismatch, ensure_ascii=False) + "\n")

    result = run_checks_for_run(run_dir)
    assert result["records"] == 14  # 2 × 7 Checks je erfolgreicher Antwort
    assert result["failed"] >= 1
    checks = [
        json.loads(line)
        for line in (run_dir / "checks.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    ids = {record["check_id"] for record in checks}
    assert "context_options_match" in ids
    mismatched = [
        record for record in checks
        if record["attempt_id"] == "attempt-0002"
        and record["check_id"] == "context_options_match"
    ]
    assert mismatched and mismatched[0]["status"] == "fail"
    # Konsistenz: Antwort ohne offenkundige Offenlegung besteht den
    # Disclosure-Check.
    ok_disclosure = [
        record for record in checks
        if record["attempt_id"] == "attempt-0001"
        and record["check_id"] == "final_answer_disclosure"
    ]
    assert ok_disclosure and ok_disclosure[0]["status"] == "pass"


def test_normalize_expression_is_whitespace_and_case_insensitive():
    assert normalize_expression("  A +  B\n") == "a + b"
