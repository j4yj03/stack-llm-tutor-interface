"""Tests für Korpus, Kontextprofile und Planung (offline)."""

import json
from pathlib import Path

import pytest

from evaluation.corpus import (
    CorpusError,
    build_request_payload,
    case_profile_eligible,
    load_cases,
    load_profiles,
    load_experiment,
    validate_experiment,
)
from evaluation.models import PROFILE_FLAG_NAMES
from evaluation.runner import build_plan

EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
DATA_DIR = EVAL_DIR / "data"


def load_default_fixtures():
    cases = load_cases(DATA_DIR / "example_cases.jsonl")
    profiles = load_profiles(DATA_DIR / "context_profiles.json")
    experiment = load_experiment(EVAL_DIR / "experiments" / "pilot.json")
    return cases, profiles, experiment


def test_example_fixtures_are_valid_and_complete():
    cases, profile_set, experiment = load_default_fixtures()
    assert cases
    assert {profile.profile_id for profile in profile_set.profiles} >= set(
        experiment.profiles
    )
    assert validate_experiment(experiment, cases, profile_set) == []
    for case in cases:
        assert case.tutor_context.question_text.strip()
        assert case.tutor_context.student_answer.strip()
        assert case.evaluation_only.provenance.response_origin == (
            "synthetic_fixture"
        )


def test_all_ten_flags_are_explicit_in_every_profile():
    profile_set = load_profiles(DATA_DIR / "context_profiles.json")
    for profile in profile_set.profiles:
        assert set(profile.flags()) == set(PROFILE_FLAG_NAMES)
        flags = profile.flags()
        # Investigationsbedingung: Score und Historie immer aus.
        assert flags["include_score"] is False
        assert flags["include_chat_history"] is False
    profile_ids = {profile.profile_id for profile in profile_set.profiles}
    assert {
        "base", "diagnosis", "feedback", "diagnosis_feedback",
        "knowledge", "steps", "solution",
    } == profile_ids
    # Profil-Semantik: kumulative Extras wie geplant.
    by_id = profile_set.by_id()
    assert by_id["feedback"].include_diagnosis_code is False
    assert by_id["diagnosis"].include_prt_feedback is False
    assert by_id["knowledge"].include_learning_goals is True
    assert by_id["steps"].include_solution_steps is True
    assert by_id["steps"].include_final_answer is False
    assert by_id["solution"].include_final_answer is True


def test_unknown_field_in_case_is_rejected(tmp_path: Path):
    line = json.loads(
        (DATA_DIR / "example_cases.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()[0]
    )
    line["tutor_context"]["unbekanntes_feld"] = True
    path = tmp_path / "case.jsonl"
    path.write_text(json.dumps(line), encoding="utf-8")
    with pytest.raises(CorpusError):
        load_cases(path)


def test_duplicate_case_id_is_rejected(tmp_path: Path):
    lines = (DATA_DIR / "example_cases.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()[:2]
    second = json.loads(lines[1])
    second["case_id"] = json.loads(lines[0])["case_id"]
    path = tmp_path / "dup.jsonl"
    path.write_text(
        lines[0] + "\n" + json.dumps(second), encoding="utf-8"
    )
    with pytest.raises(CorpusError):
        load_cases(path)


def test_missing_profile_data_excludes_case():
    cases, profile_set, _experiment = load_default_fixtures()
    by_id = profile_set.by_id()
    base_case = next(
        case for case in cases
        if case.case_id == "chain-exp-missing-inner-001"
    )
    # base/diagnosis/diagnosis_feedback sind datenseitig belegt; knowledge
    # auch (gemeinsamer Effekt von Ziele+Regeln, kein Einzelisolat).
    assert case_profile_eligible(base_case, by_id["base"], True) is None
    assert case_profile_eligible(base_case, by_id["diagnosis"], True) is None
    assert case_profile_eligible(
        base_case, by_id["diagnosis_feedback"], True
    ) is None
    assert case_profile_eligible(base_case, by_id["knowledge"], True) is None
    # Fehlende verifizierte Schritte schließen die Lösungs-Profile aus;
    # kein stiller Fallback auf kleinere Kontexte. (Die Kette-Fixture
    # trägt Schritte; die Kontroll-Fälle ohne Diagnose haben keine.)
    assert case_profile_eligible(base_case, by_id["steps"], True) is None
    assert case_profile_eligible(base_case, by_id["solution"], True) is None
    correct_case = next(
        case for case in cases if case.case_id == "prod-correct-001"
    )
    assert case_profile_eligible(correct_case, by_id["steps"], True) is not None
    assert case_profile_eligible(
        correct_case, by_id["solution"], True
    ) is not None
    # Lizenzprüfung: Nicht verifizierte Mathematik sperrt Forschungsläufe.
    assert base_case.is_research_eligible(False) is False
    assert base_case.is_research_eligible(True) is True
    assert case_profile_eligible(
        base_case, by_id["base"], False
    ) == "Mathematik nicht verifiziert (mathematics_status=pending)"
    # Ohne Diagnose/Feedback entfallen deren Profile (datenseitig).
    assert case_profile_eligible(correct_case, by_id["diagnosis"], True) is not None
    assert case_profile_eligible(correct_case, by_id["feedback"], True) is not None


def test_request_payload_keeps_evaluation_only_out_of_context():
    cases, profile_set, _experiment = load_default_fixtures()
    case = cases[0]
    profile = profile_set.by_id()["base"]
    payload = build_request_payload(case, profile, 1, None)
    stacked = payload["stack"]
    assert stacked["diagnosis_code"] is None
    assert stacked["prt_feedback"] is None
    assert stacked["solution_steps"] == []
    assert stacked["final_answer"] is None
    assert payload["chat_id"] is None
    assert payload["user_message"] is None
    assert "model" not in payload
    assert len(payload["context_options"]) == 10


def test_request_payload_supplies_guard_answer_with_steps():
    cases, profile_set, _experiment = load_default_fixtures()
    case = next(
        item for item in cases
        if item.case_id == "chain-exp-missing-inner-001"
    )
    profile = profile_set.by_id()["steps"]
    payload = build_request_payload(case, profile, 3, "some-model")
    stack = payload["stack"]
    # Schritte aus verifizierter Referenz + Guard-Endlösung für den
    # serverseitigen Literal-Schutz (Prompt bleibt final_answer-frei).
    assert stack["solution_steps"]
    assert stack["final_answer"] == case.evaluation_only.reference.final_answer
    assert payload["context_options"]["include_final_answer"] is False
    assert payload["model"] == "some-model"


def test_plan_is_deterministic_and_controls_are_appended():
    cases, profile_set, experiment = load_default_fixtures()
    jobs_a, exclusions_a = build_plan(experiment, cases, DATA_DIR / "context_profiles.json")
    jobs_b, exclusions_b = build_plan(experiment, cases, DATA_DIR / "context_profiles.json")
    assert jobs_a == jobs_b
    assert [job["job_id"] for job in jobs_a] == [
        "job-" + str(index).zfill(4)
        for index in range(1, len(jobs_a) + 1)
    ]
    assert exclusions_a == exclusions_b
    # Erwartete Haupt-Jobs dynamisch herleiten (Raster × Eignung).
    by_id = profile_set.by_id()
    expected_main = 0
    for case in cases:
        for profile_id in experiment.profiles:
            if case_profile_eligible(case, by_id[profile_id], experiment.allow_unverified_cases) is None:
                expected_main += len(experiment.hint_levels) * experiment.repetitions
    mains = [job for job in jobs_a if job["block"] == "main"]
    controls = [job for job in jobs_a if job["block"] == "control"]
    assert len(mains) == expected_main
    assert len(controls) == len(experiment.control_jobs)
    # Kontrolljobs stehen am Ende des Plans.
    assert jobs_a[-1]["block"] == "control"
    # Ausgeschlossene Rasterzellen sind pro (Fall, Profil, Stufe) dokumentiert.
    reasons = {
        (entry["case_id"], entry["profile_id"])
        for entry in exclusions_a
    }
    assert any(
        profile_id in ("diagnosis", "feedback", "diagnosis_feedback")
        for _case, profile_id in reasons
    )
