"""Tests der automatischen Prüfungen (checks.py) — offline.

Verwendet den echten Fallbestand und die echte Stufen-Policy; sympy
ist optional, die Tests tolerant.
"""

import json
from pathlib import Path

import pytest

from evaluation.checks import (
    _extract_candidate_expressions,
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


@pytest.mark.parametrize("prompt_messages", [
    None, [], {}, [None],
    [{"role": "system", "content": "policy"}],
    [{"role": "user", "content": None}],
    [{"role": "user", "content": "  "}],
])
def test_missing_real_prompt_is_inconclusive(prompt_messages):
    generation = make_generation("Ein Hinweis.")
    generation["returned"].pop("prompt_messages")
    if prompt_messages is not None:
        generation["returned"]["prompt_messages"] = prompt_messages
    records = run_checks(generation, CASE, PROFILES["steps"], POLICY)
    for check_id in ("prompt_required_content", "prompt_solution_guard"):
        record = check_by_id(records, check_id)
        assert record["status"] == "inconclusive"
        assert record["evidence"]["prompt_available"] is False
        assert record["reason"]


def test_score_profile_requires_an_actual_score_section():
    profile = PROFILES["steps"].model_copy(update={"include_score": True})
    generation = make_generation("Pruefe die innere Ableitung.")
    records = run_checks(generation, CASE, profile, POLICY)
    required = check_by_id(records, "prompt_required_content")
    assert required["status"] == "fail"
    assert "score" in required["evidence"]["missing"]
    generation["returned"]["prompt_messages"][-1]["content"] += "\nSTACK-SCORE:\n0.0"
    records = run_checks(generation, CASE, profile, POLICY)
    assert check_by_id(records, "prompt_required_content")["status"] == "pass"


@pytest.mark.parametrize("level", [3, 4])
@pytest.mark.parametrize("include_final", [False, True])
def test_prompt_final_answer_needs_both_permissions(level, include_final):
    profile = PROFILES["solution" if include_final else "steps"]
    generation = make_generation("Ein Hinweis.", level=level)
    payload = build_request_payload(CASE, profile, level, "test-model")
    generation["request_payload"] = payload
    generation["returned"]["context_options"] = payload["context_options"]
    generation["returned"]["prompt_messages"][1]["content"] += " " + FINAL
    guard = check_by_id(
        run_checks(generation, CASE, profile, POLICY), "prompt_solution_guard"
    )
    allowed = include_final and level == 4
    assert guard["status"] == ("pass" if allowed else "fail")
    assert guard["evidence"]["final_locked"] is not allowed


@pytest.mark.parametrize("case_id", [
    "prod-correct-001", "chain-correct-equivalent-001",
])
def test_correct_student_answer_is_not_a_prompt_solution_leak(case_id):
    case = CASES[case_id]
    profile = PROFILES["base"]
    generation = make_generation("Ein Hinweis.")
    payload = build_request_payload(case, profile, 3, "test-model")
    generation.update(
        case_id=case.case_id, profile_id=profile.profile_id, request_payload=payload
    )
    generation["returned"].update(
        question_id=case.tutor_context.question_id,
        context_options=payload["context_options"],
        prompt_messages=[
            {"role": "system", "content": "policy"},
            {"role": "user", "content": (
                case.tutor_context.question_text + "\n<student_answer>\n"
                + case.tutor_context.student_answer + "\n</student_answer>"
            )},
        ],
    )
    records = run_checks(generation, case, profile, POLICY)
    assert check_by_id(records, "prompt_required_content")["status"] == "pass"
    assert check_by_id(records, "prompt_solution_guard")["status"] == "pass"
    # The same answer outside student input must still trigger the guard.
    generation["returned"]["prompt_messages"][1]["content"] += (
        "\nsolution section: " + case.tutor_context.student_answer
    )
    guard = check_by_id(
        run_checks(generation, case, profile, POLICY), "prompt_solution_guard"
    )
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


@pytest.mark.parametrize("hint", [
    "Pruefe die innere Ableitung.", "`x+1`", r"$\frac{1}{2}$",
])
@pytest.mark.parametrize("level", [3, 4])
def test_no_positive_disclosure_match_is_inconclusive(hint, level):
    disclosure = check_by_id(
        run_checks(make_generation(hint, level), CASE, PROFILES["steps"], POLICY),
        "final_answer_disclosure",
    )
    assert disclosure["status"] == "inconclusive"
    assert disclosure["evidence"]["present"] is None


@pytest.mark.parametrize("wrapper", [
    "`{}`", "```math\n{}\n```", "${}$", "$$ {} $$",
    r"\({}\)", r"\[{}\]", "\nf'(x) = {}\n",
])
def test_symbolic_disclosure_from_explicit_math(wrapper):
    pytest.importorskip("sympy")
    expression = "-5*(2*x-2*exp(x))*exp(x*x-2*exp(x))"
    hint = "Pruefe diese Formel: " + wrapper.format(expression)
    for level in (3, 4):
        disclosure = check_by_id(
            run_checks(make_generation(hint, level), CASE, PROFILES["steps"], POLICY),
            "final_answer_disclosure",
        )
        assert disclosure["status"] == ("pass" if level == 4 else "fail")
        assert disclosure["evidence"]["present"] is True
        assert disclosure["evidence"]["match_kind"] == "symbolic"


def test_expression_extraction_does_not_parse_prose_fragments():
    assert _extract_candidate_expressions("Pruefe x+1 und dann x^2.") == []
    assert _extract_candidate_expressions("x+1\nErgebnis: `2*x`", limit=1) == ["2*x"]
    assert _extract_candidate_expressions(r"$\frac{1}{2}$") == []


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


@pytest.mark.parametrize("candidate,reference,variable", [
    ("x+x", "2*x", "x"),
    ("sin(x)^2+cos(x)^2", "1", "x"),
    ("tan(x)", "sin(x)/cos(x)", "x"),
    ("sqrt(4)+log(E)+cos(pi)", "2", "x"),
    ("e^x", "exp(x)", "x"),
    ("x^(1/2)", "sqrt(x)", "x"),
    ("0.1+0.2", "3/10", "x"),
    ("t*t", "t^2", "t"),
])
def test_safe_parser_normal_equivalence(candidate, reference, variable):
    pytest.importorskip("sympy")
    equivalent, reason = symbolic_equivalence(candidate, reference, variable)
    assert equivalent is True, reason
    assert symbolic_equivalence("x+1", "x")[0] is False


@pytest.mark.parametrize("expression", [
    "__import__('os').getcwd()", "x.__class__", "sin(x).__class__",
    "factorial(1000000)", "Symbol('x')", "open('file')", "x[0]",
    "sin(x, evaluate=True)", "(lambda: x)()", "[x for x in (1,)]",
    "import os", "x; x", "unknown(x)", "die innere Ableitung", "x+",
    "10^1000000", "10^(10^10)", "(x+1)^16", "sqrt(999983^16+1)", "x^(1/999983)",
    "exp(exp(1000000))", "exp(exp(10))", "exp(exp(exp(x)))",
    "E^(E^(E^x))", "E^x+" * 6 + "E^x", "((x+sin(x)+cos(x))^4+1)^4",
    "1e1000000000", "1/0", "sin(" * 13 + "x" + ")" * 13,
    "x+" * 40 + "x", "x" * 201,
])
def test_safe_parser_rejects_attacks_and_limits(expression, monkeypatch):
    sympy = pytest.importorskip("sympy")
    calls = []

    def unexpected(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Rejected syntax must not reach SymPy evaluation")

    monkeypatch.setattr(sympy, "factorial", unexpected)
    monkeypatch.setattr(sympy, "simplify", unexpected)
    for candidate, reference in ((expression, "x"), ("x", expression)):
        equivalent, reason = symbolic_equivalence(candidate, reference)
        assert equivalent is None, reason
    assert calls == []


def test_sympy_remains_optional(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "sympy", None)
    assert symbolic_equivalence("x+x", "2*x")[0] is None
    records = run_checks(make_generation("`x+1`"), CASE, PROFILES["steps"], POLICY)
    disclosure = check_by_id(records, "final_answer_disclosure")
    assert disclosure["status"] == "inconclusive"
    assert disclosure["evidence"]["present"] is None
    assert disclosure["evidence"]["sympy_available"] is False
    records = run_checks(make_generation(FINAL), CASE, PROFILES["steps"], POLICY)
    assert check_by_id(records, "final_answer_disclosure")["status"] == "fail"


def test_failed_generation_is_not_checkable():
    records = run_checks(
        {"outcome": "server_error", "hint_level": 3},
        CASE, PROFILES["steps"], POLICY
    )
    assert len(records) == 1
    assert records[0]["check_id"] == "response_available"
    assert records[0]["status"] == "not_applicable"


def test_run_checks_for_run_writes_checks_file(tmp_path: Path, monkeypatch):
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

    # Manifest inputs are CODE_DIR-relative, independent of the notebook cwd.
    monkeypatch.chdir(EVAL_DIR / "notebooks")
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
    # No positive match cannot establish absence of disclosure.
    ok_disclosure = [
        record for record in checks
        if record["attempt_id"] == "attempt-0001"
        and record["check_id"] == "final_answer_disclosure"
    ]
    assert ok_disclosure and ok_disclosure[0]["status"] == "inconclusive"
    assert ok_disclosure[0]["evidence"]["present"] is None


def test_normalize_expression_is_whitespace_and_case_insensitive():
    assert normalize_expression("  A +  B\n") == "a + b"
