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
    assert len(cases) == 12
    assert {case.task_instance_id for case in cases} == {
        "synthetic-chain-exp-f1", "synthetic-chain-exp-f2",
        "synthetic-prod-f1", "synthetic-prod-f2",
    }
    assert len({case.tutor_context.question_text for case in cases}) == 4
    assert {
        "chain-exp-missing-inner-001",
        "chain-exp-wrong-inner-exp-001",
        "chain-exp-missing-constant-001",
        "prod-missing-term-001",
        "prod-wrong-power-001",
        "prod-correct-001",
        "chain-correct-equivalent-001",
        "robustness-prompt-injection-001",
    } <= {case.case_id for case in cases}
    assert {profile.profile_id for profile in profile_set.profiles} >= set(
        experiment.profiles
    )
    assert validate_experiment(experiment, cases, profile_set) == []
    for case in cases:
        assert case.readiness == "draft"
        assert case.tutor_context.question_text.strip()
        assert case.tutor_context.student_answer.strip()
        assert case.tutor_context.solution_steps == []
        assert case.tutor_context.final_answer is None
        assert case.evaluation_only.instance.instance_id == case.task_instance_id
        assert case.evaluation_only.reference.expected_diagnosis == (
            case.tutor_context.diagnosis_code
        )
        assert case.evaluation_only.verification.model_dump() == {
            "mathematics_status": "pending",
            "diagnosis_status": "pending",
            "method": None,
            "tool_and_version": None,
            "reviewer_id": None,
            "evidence_refs": [],
        }
        assert case.evaluation_only.provenance.response_origin == (
            "synthetic_fixture"
        )
        assert case.evaluation_only.provenance.question_export_ref is None
        assert case.evaluation_only.provenance.prt_test_result_ref is None
        assert case.evaluation_only.provenance.student_attempt_ref is None
        assert case.is_research_eligible(False) is False


@pytest.mark.parametrize(
    "case_id, diagnosis, student_answer, feedback_fragment",
    [
        (
            "prod-wrong-power-001", "wrong_derivative_power",
            "x*sin(x)+x^2*cos(x)", "Potenzregel",
        ),
        (
            "chain-exp-missing-inner-002",
            "missing_chain_rule_inner_derivative",
            "3*exp(2*x+1)", "innere Ableitung",
        ),
        (
            "chain-exp-missing-constant-002", "missing_constant_factor",
            "2*exp(2*x+1)", "konstante Faktor 3",
        ),
        (
            "prod-missing-term-002", "missing_product_rule_term",
            "3*x^2*exp(x)", "Summand",
        ),
        (
            "prod-wrong-power-002", "wrong_derivative_power",
            "x^2*exp(x)+x^3*exp(x)", "Potenzregel",
        ),
    ],
)
def test_error_fixtures_match_their_synthetic_diagnoses(
    case_id, diagnosis, student_answer, feedback_fragment
):
    cases = {case.case_id: case for case in
             load_cases(DATA_DIR / "example_cases.jsonl")}
    case = cases[case_id]
    context = case.tutor_context
    reference = case.evaluation_only.reference
    assert context.student_answer == student_answer
    assert context.diagnosis_code == reference.expected_diagnosis == diagnosis
    assert feedback_fragment in context.prt_feedback
    assert reference.expected_input_validity == "valid"
    assert reference.expected_correctness == "incorrect"
    assert context.score == 0.0


@pytest.mark.parametrize(
    "instance_id, question_id, function, final_answer, equivalents, step_markers",
    [
        (
            "synthetic-chain-exp-f2", "ableitung_kettenregel_exp_001",
            "3*exp(2*x+1)", "6*exp(2*x+1)",
            ["3*exp(2*x+1)*2", "6*exp(1)*exp(2*x)"],
            [
                "konstanten Faktor 3", "g(x)=2*x+1", "g'(x)=2",
                "3*exp(g(x))*g'(x)", "6*exp(2*x+1)",
            ],
        ),
        (
            "synthetic-prod-f2", "ableitung_produktregel_001",
            "x^3*exp(x)", "3*x^2*exp(x)+x^3*exp(x)",
            ["x^2*(x+3)*exp(x)", "(x^3+3*x^2)*exp(x)"],
            [
                "u(x)=x^3", "u'(x)*v(x)+u(x)*v'(x)", "u'(x)=3*x^2",
                "3*x^2*exp(x)+x^3*exp(x)", "x^2*(x+3)*exp(x)",
            ],
        ),
    ],
)
def test_variant_fixtures_use_their_own_local_references(
    instance_id, question_id, function, final_answer, equivalents, step_markers
):
    cases = [case for case in load_cases(DATA_DIR / "example_cases.jsonl")
             if case.task_instance_id == instance_id]
    assert len(cases) == 2
    first_reference = cases[0].evaluation_only.reference.model_dump(
        exclude={"expected_diagnosis"}
    )
    for case in cases:
        context = case.tutor_context
        reference = case.evaluation_only.reference
        assert context.question_id == question_id
        assert "f(x)=" + function in context.question_text
        assert context.learning_goals
        assert context.math_rules
        assert reference.final_answer == final_answer
        assert reference.equivalent_forms == equivalents
        assert len(reference.solution_steps) == len(step_markers)
        for step, marker in zip(reference.solution_steps, step_markers):
            assert marker in step
        assert reference.model_dump(exclude={"expected_diagnosis"}) == (
            first_reference
        )
        assert case.evaluation_only.provenance.instantiated_task_ref is None
        assert json.dumps(case.model_dump(), ensure_ascii=False).isascii()


def test_example_fixture_mathematics_with_optional_sympy():
    """Lokale Plausibilitaet, keine STACK- oder PRT-Verifizierung."""
    sympy = pytest.importorskip(
        "sympy", reason="Optional symbolic fixture checks require sympy"
    )
    x = sympy.Symbol("x", real=True)
    functions = {
        "synthetic-chain-exp-f1": "-5*exp(x^2-2*exp(x))",
        "synthetic-chain-exp-f2": "3*exp(2*x+1)",
        "synthetic-prod-f1": "x^2*sin(x)",
        "synthetic-prod-f2": "x^3*exp(x)",
    }
    for case in load_cases(DATA_DIR / "example_cases.jsonl"):
        reference = case.evaluation_only.reference
        function = sympy.sympify(
            functions[case.task_instance_id].replace("^", "**"), locals={"x": x}
        )
        derivative = sympy.diff(function, x)
        for formula in [reference.final_answer] + reference.equivalent_forms:
            expression = sympy.sympify(
                formula.replace("^", "**"), locals={"x": x}
            )
            assert sympy.simplify(expression - derivative) == 0, case.case_id
        if reference.expected_input_validity == "valid":
            answer = sympy.sympify(
                case.tutor_context.student_answer.replace("^", "**"),
                locals={"x": x},
            )
            is_correct = sympy.simplify(answer - derivative) == 0
            assert is_correct == (
                reference.expected_correctness == "correct"
            ), case.case_id


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


def test_steps_profile_requires_the_guard_reference_and_score_requires_a_value():
    cases, profiles, _ = load_default_fixtures()
    case = cases[0].model_copy(deep=True)
    case.evaluation_only.reference.final_answer = None
    assert "Guard" in case_profile_eligible(case, profiles.by_id()["steps"], True)
    score_profile = profiles.by_id()["base"].model_copy(update={"include_score": True})
    case.tutor_context.score = None
    assert case_profile_eligible(case, score_profile, True) == "score fehlt im Fall"
    case.tutor_context.score = 0.0
    assert case_profile_eligible(case, score_profile, True) is None


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
