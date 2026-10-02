"""Offline checks of authored task cases, not STACK/PRT verification."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from evaluation.corpus import (
    CorpusError,
    build_request_payload,
    case_profile_eligible,
    load_cases,
    load_profiles,
)
from evaluation.task_cases import cases_from_tasks, task_source_hashes, write_task_cases

TASKS_DIR = CODE_DIR / "tasks"
SCHEMA_PATH = CODE_DIR / "schemas" / "stack_ai_tutor_task.schema.json"
CHAIN_FILE = "ableitung_kettenregel_exp_001.json"
PRODUCT_FILE = "ableitung_produktregel_001.json"


@pytest.fixture
def copied_tasks(tmp_path: Path) -> Path:
    target = tmp_path / "tasks"
    target.mkdir()
    for source in TASKS_DIR.glob("*.json"):
        (target / source.name).write_bytes(source.read_bytes())
    return target


def save_task(path: Path, task: dict) -> None:
    path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")


def test_all_task_categories_have_explicit_instance_bound_cases():
    cases = cases_from_tasks(TASKS_DIR)
    assert len(cases) == 15
    assert len({case.case_id for case in cases}) == 15
    expected_instances = {
        CHAIN_FILE: ("task-chain-exp-f1", "f(x)=-5*exp(x^2-2*exp(x))", 9),
        PRODUCT_FILE: ("task-prod-f1", "f(x)=x^2*sin(x)", 6),
    }
    for filename, (instance_id, function, count) in expected_instances.items():
        task = json.loads((TASKS_DIR / filename).read_text(encoding="utf-8"))
        examples = task["evaluation_examples"]
        assert examples["instance_id"] == instance_id
        assert examples["function"] == function
        selected = [case for case in cases if case.task_instance_id == instance_id]
        assert len(selected) == count
        assert {
            case.evaluation_only.reference.expected_diagnosis for case in selected
        } == set(task["diagnoses"]) | {None}
        for case, answer in zip(selected, examples["answers"]):
            assert case.case_id == answer["case_id"]
            assert case.tutor_context.question_id == task["question_id"]
            assert case.tutor_context.question_text == task["question_text_template"].replace(
                "{funktion}", function
            )
            assert case.tutor_context.student_answer == answer["student_answer"]
            assert case.evaluation_only.reference.expected_diagnosis == answer.get("expected_error")
            assert case.evaluation_only.instance.instance_id == instance_id
            assert case.evaluation_only.reference.final_answer == task["model_solution"]["final_answer"]
    existing = load_cases(CODE_DIR / "evaluation" / "data" / "example_cases.jsonl")
    assert len(existing) == 12
    assert not ({case.case_id for case in cases} & {case.case_id for case in existing})


def test_references_stay_evaluation_only_and_all_evidence_stays_pending():
    tasks = {
        task["question_id"]: (path, task)
        for path in TASKS_DIR.glob("*.json")
        for task in [json.loads(path.read_text(encoding="utf-8"))]
    }
    for case in cases_from_tasks(TASKS_DIR):
        path, task = tasks[case.tutor_context.question_id]
        context = case.tutor_context
        reference = case.evaluation_only.reference
        assert case.schema_version == "1.0"
        assert case.readiness == "draft"
        assert context.score is None
        assert context.seed is None
        assert context.solution_steps == []
        assert context.final_answer is None
        assert context.math_rules == []
        assert context.learning_goals == task["learning_goals"]
        assert reference.equivalent_forms == task["model_solution"]["equivalent_forms"]
        assert reference.solution_steps == [
            step["description"] + " Formel: " + step["formula"]
            for step in task["model_solution"]["solution_steps"]
        ]
        assert case.evaluation_only.instance.seed is None
        assert case.evaluation_only.instance.variable == "x"
        assert case.evaluation_only.instance.domain_assumptions == []
        assert case.evaluation_only.verification.model_dump() == {
            "mathematics_status": "pending",
            "diagnosis_status": "pending",
            "method": None,
            "tool_and_version": None,
            "reviewer_id": None,
            "evidence_refs": [],
        }
        assert case.evaluation_only.provenance.model_dump() == {
            "response_origin": "synthetic_fixture",
            "question_export_ref": None,
            "instantiated_task_ref": "tasks/" + path.name + "#evaluation_examples",
            "prt_test_result_ref": None,
            "student_attempt_ref": None,
        }
        assert case.is_research_eligible(False) is False
        if context.diagnosis_code is None:
            assert context.prt_feedback is None
            assert reference.expected_correctness == "correct"
        else:
            assert "Synthetischer Fehlerkontext" in context.prt_feedback
            assert context.prt_feedback.endswith(task["diagnoses"][context.diagnosis_code]["title"])
        if context.diagnosis_code == "syntax_error":
            assert reference.expected_input_validity == "invalid"
            assert reference.expected_correctness == "unknown"
        if context.diagnosis_code == "unknown_error":
            assert context.student_answer == "42"
            assert reference.expected_input_validity == "valid"
            assert reference.expected_correctness == "incorrect"


def test_missing_vs_provided_synthetic_error_uses_existing_payload_contract():
    profiles = load_profiles(CODE_DIR / "evaluation" / "data" / "context_profiles.json").by_id()
    case = cases_from_tasks(TASKS_DIR)[0]
    base = build_request_payload(case, profiles["base"], 1, None)
    provided = build_request_payload(case, profiles["diagnosis_feedback"], 1, None)
    assert base["stack"]["diagnosis_code"] is None
    assert base["stack"]["prt_feedback"] is None
    assert provided["stack"]["diagnosis_code"] == case.evaluation_only.reference.expected_diagnosis
    assert "Synthetischer Fehlerkontext" in provided["stack"]["prt_feedback"]
    for payload in (base, provided):
        assert payload["stack"]["score"] is None
        assert payload["stack"]["solution_steps"] == []
        assert payload["stack"]["final_answer"] is None
        assert payload["chat_id"] is None
        assert payload["user_message"] is None
        assert "evaluation_only" not in payload
    assert case_profile_eligible(case, profiles["diagnosis_feedback"], True) is None
    assert case_profile_eligible(case, profiles["knowledge"], True) == "math_rules fehlen im Fall"
    assert case_profile_eligible(
        case, profiles["base"].model_copy(update={"include_score": True}), True
    ) == "score fehlt im Fall"
    steps_profile = profiles["base"].model_copy(update={"include_solution_steps": True})
    assert case_profile_eligible(case, steps_profile, True) is None
    guarded = build_request_payload(case, steps_profile, 3, None)
    assert guarded["stack"]["solution_steps"] == case.evaluation_only.reference.solution_steps
    assert guarded["stack"]["final_answer"] == case.evaluation_only.reference.final_answer
    assert guarded["context_options"]["include_final_answer"] is False


@pytest.mark.parametrize("omit", [False, True])
def test_absent_expected_error_is_not_inferred(copied_tasks: Path, omit: bool):
    path = copied_tasks / CHAIN_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    answer = task["evaluation_examples"]["answers"][0]
    if omit:
        del answer["expected_error"]
    else:
        answer["expected_error"] = None
    save_task(path, task)
    case = cases_from_tasks(copied_tasks)[0]
    assert case.tutor_context.student_answer == "-5*exp(x^2-2*exp(x))"
    assert case.tutor_context.diagnosis_code is None
    assert case.tutor_context.prt_feedback is None
    assert case.evaluation_only.reference.expected_diagnosis is None
    assert case.evaluation_only.reference.expected_correctness == "incorrect"


def test_examples_are_optional_but_tasks_without_them_are_still_validated(copied_tasks: Path):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for path in copied_tasks.glob("*.json"):
        task = json.loads(path.read_text(encoding="utf-8"))
        del task["evaluation_examples"]
        Draft202012Validator(schema).validate(task)
        save_task(path, task)
    assert cases_from_tasks(copied_tasks) == []
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    task["unexpected_property"] = True
    save_task(path, task)
    with pytest.raises(CorpusError, match=PRODUCT_FILE):
        cases_from_tasks(copied_tasks)
    with pytest.raises(CorpusError, match=PRODUCT_FILE):
        task_source_hashes(copied_tasks)


@pytest.mark.parametrize(
    "field_path, value",
    [
        (("evaluation_examples",), None),
        (("evaluation_examples", "instance_id"), "bad id"),
        (("evaluation_examples", "function"), " "),
        (("evaluation_examples", "unexpected"), True),
        (("evaluation_examples", "answers"), []),
        (("evaluation_examples", "answers", 0, "case_id"), "bad id"),
        (("evaluation_examples", "answers", 0, "student_answer"), " "),
        (("evaluation_examples", "answers", 0, "expected_error"), 42),
        (("evaluation_examples", "answers", 0, "expected_input_validity"), "probably"),
        (("evaluation_examples", "answers", 0, "expected_correctness"), "probably"),
        (("evaluation_examples", "answers", 0, "unexpected"), True),
    ],
)
def test_examples_reject_schema_invalid_data(copied_tasks: Path, field_path: tuple, value):
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    node = task
    for key in field_path[:-1]:
        node = node[key]
    node[field_path[-1]] = value
    save_task(path, task)
    with pytest.raises(CorpusError, match="Invalid task.*" + PRODUCT_FILE):
        cases_from_tasks(copied_tasks)


@pytest.mark.parametrize("field", ["case_id", "student_answer", "expected_input_validity", "expected_correctness"])
def test_answer_requires_explicit_fields(copied_tasks: Path, field: str):
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    del task["evaluation_examples"]["answers"][0][field]
    save_task(path, task)
    with pytest.raises(CorpusError, match=field):
        cases_from_tasks(copied_tasks)


def test_error_key_must_belong_to_its_own_task(copied_tasks: Path):
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    task["evaluation_examples"]["answers"][0]["expected_error"] = "only_inner_derivative"
    save_task(path, task)
    with pytest.raises(CorpusError, match="expected_error.*only_inner_derivative"):
        cases_from_tasks(copied_tasks)


@pytest.mark.parametrize("identifier", ["question_id", "instance_id", "case_id"])
def test_duplicate_ids_across_tasks_are_rejected(copied_tasks: Path, identifier: str):
    chain = json.loads((copied_tasks / CHAIN_FILE).read_text(encoding="utf-8"))
    path = copied_tasks / PRODUCT_FILE
    product = json.loads(path.read_text(encoding="utf-8"))
    if identifier == "question_id":
        product[identifier] = chain[identifier]
        del product["evaluation_examples"]
    elif identifier == "instance_id":
        product["evaluation_examples"][identifier] = chain["evaluation_examples"][identifier]
    else:
        product["evaluation_examples"]["answers"][0][identifier] = chain["evaluation_examples"]["answers"][0][identifier]
    save_task(path, product)
    with pytest.raises(CorpusError, match="Duplicate " + identifier):
        cases_from_tasks(copied_tasks)


def test_duplicate_ids_within_answers_are_rejected(copied_tasks: Path):
    path = copied_tasks / CHAIN_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    task["evaluation_examples"]["answers"].append(deepcopy(task["evaluation_examples"]["answers"][0]))
    save_task(path, task)
    with pytest.raises(CorpusError, match="Duplicate case_id"):
        cases_from_tasks(copied_tasks)


@pytest.mark.parametrize("template", [None, "No instantiated function here."])
def test_instance_requires_a_usable_template(copied_tasks: Path, template):
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    if template is None:
        del task["question_text_template"]
    else:
        task["question_text_template"] = template
    save_task(path, task)
    with pytest.raises(CorpusError, match="question_text_template"):
        cases_from_tasks(copied_tasks)


def test_missing_empty_and_malformed_sources_fail(tmp_path: Path, copied_tasks: Path):
    with pytest.raises(CorpusError, match="directory not found"):
        cases_from_tasks(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CorpusError, match="No task JSON"):
        cases_from_tasks(empty)
    (copied_tasks / PRODUCT_FILE).write_text("{", encoding="utf-8")
    with pytest.raises(CorpusError, match="Invalid task JSON.*" + PRODUCT_FILE):
        cases_from_tasks(copied_tasks)
    with pytest.raises(CorpusError, match="Invalid task schema"):
        cases_from_tasks(TASKS_DIR, tmp_path / "missing-schema.json")
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text('{"type": "not_a_schema_type"}', encoding="utf-8")
    with pytest.raises(CorpusError, match="Invalid task schema"):
        cases_from_tasks(TASKS_DIR, invalid_schema)


def test_cases_hashes_and_jsonl_are_deterministic(tmp_path: Path, copied_tasks: Path):
    cases = cases_from_tasks(copied_tasks)
    assert cases == cases_from_tasks(copied_tasks, SCHEMA_PATH)
    hashes = task_source_hashes(copied_tasks)
    assert list(hashes) == sorted(hashes)
    assert hashes == {
        "tasks/" + path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(copied_tasks.glob("*.json"))
    }
    for case in cases:
        source_ref = case.evaluation_only.provenance.instantiated_task_ref.split("#")[0]
        assert source_ref in hashes
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_task_cases(cases, first)
    write_task_cases(cases_from_tasks(copied_tasks), second)
    assert first.read_bytes() == second.read_bytes()
    assert load_cases(first) == cases
    path = copied_tasks / CHAIN_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    task["evaluation_examples"]["answers"][0]["student_answer"] = "0"
    save_task(path, task)
    changed = task_source_hashes(copied_tasks)
    assert changed["tasks/" + CHAIN_FILE] != hashes["tasks/" + CHAIN_FILE]
    assert changed["tasks/" + PRODUCT_FILE] == hashes["tasks/" + PRODUCT_FILE]


def test_writer_requires_explicit_overwrite(tmp_path: Path):
    output = tmp_path / "cases.jsonl"
    output.write_text("existing content", encoding="utf-8")
    cases = cases_from_tasks(TASKS_DIR)
    with pytest.raises(FileExistsError):
        write_task_cases(cases, output)
    assert output.read_text(encoding="utf-8") == "existing content"
    write_task_cases(cases, output, overwrite=True)
    assert load_cases(output) == cases


@pytest.mark.parametrize("problem", ["empty", "duplicate", "invalid"])
def test_writer_validates_before_touching_existing_output(tmp_path: Path, problem: str):
    output = tmp_path / "cases.jsonl"
    output.write_text("existing content", encoding="utf-8")
    cases = cases_from_tasks(TASKS_DIR)
    if problem == "empty":
        cases = []
    elif problem == "duplicate":
        cases.append(cases[0])
    else:
        cases[-1].case_id = "bad id"
    with pytest.raises(CorpusError):
        write_task_cases(cases, output, overwrite=True)
    assert output.read_text(encoding="utf-8") == "existing content"


def test_cli_exports_only_on_request_and_preserves_existing_files(tmp_path: Path, copied_tasks: Path, capsys):
    from evaluation.__main__ import main

    output = tmp_path / "cases.jsonl"
    argv = [
        "cases-from-tasks", "--tasks-dir", str(copied_tasks),
        "--schema-path", str(SCHEMA_PATH), "--output", str(output),
    ]
    assert main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["cases"] == 15
    assert result["source_task_hashes"] == task_source_hashes(copied_tasks)
    assert result["mathematics_status"] == result["diagnosis_status"] == "pending"
    original = output.read_bytes()
    assert main(argv) == 2
    assert "FEHLER" in capsys.readouterr().err
    assert output.read_bytes() == original
    assert main(argv + ["--overwrite"]) == 0
    capsys.readouterr()
    path = copied_tasks / PRODUCT_FILE
    task = json.loads(path.read_text(encoding="utf-8"))
    task["evaluation_examples"]["answers"][0]["expected_error"] = "not_a_diagnosis"
    save_task(path, task)
    assert main(argv + ["--overwrite"]) == 2
    assert "expected_error" in capsys.readouterr().err
    assert output.read_bytes() == original
    missing_output = tmp_path / "not-created.jsonl"
    assert main(argv[:-1] + [str(missing_output)]) == 2
    assert not missing_output.exists()


def test_converter_and_cli_do_not_import_server_or_use_network_or_database(tmp_path: Path):
    script = '''
import importlib.abc
import socket
import sqlite3
import sys
from pathlib import Path

class RejectServerImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app" or fullname.startswith("app."):
            raise AssertionError("Server import: " + fullname)

def forbidden(*args, **kwargs):
    raise AssertionError("Network or database operation")

sys.meta_path.insert(0, RejectServerImports())
socket.socket.connect = forbidden
sqlite3.connect = forbidden
from evaluation.task_cases import cases_from_tasks
assert len(cases_from_tasks(Path("tasks"))) == 15
from evaluation.__main__ import main
assert main(["cases-from-tasks", "--output", sys.argv[1]]) == 0
assert "app.main" not in sys.modules
'''
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "safe.jsonl")],
        cwd=CODE_DIR, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_instance_mathematics_with_optional_bounded_sympy():
    """Local plausibility only; these checks do not release synthetic cases."""
    sympy = pytest.importorskip("sympy", reason="Optional bounded symbolic plausibility checks")
    from evaluation.checks import symbolic_equivalence

    x = sympy.Symbol("x")
    outer = -5 * sympy.exp(x**2 - 2 * sympy.exp(x))
    inner_derivative = 2*x - 2*sympy.exp(x)
    instances = {
        "task-chain-exp-f1": outer,
        "task-prod-f1": x**2 * sympy.sin(x),
    }
    error_answers = {
        "task-chain-exp-f1": {
            "missing_chain_rule_inner_derivative": outer,
            "wrong_derivative_inner_exp": outer * (2*x - 2),
            "wrong_derivative_power": outer * (x - 2*sympy.exp(x)),
            "missing_constant_factor": sympy.exp(x**2 - 2*sympy.exp(x)) * inner_derivative,
            "sign_error": outer * (2*x + 2*sympy.exp(x)),
            "only_inner_derivative": inner_derivative,
            "unknown_error": sympy.Integer(42),
        },
        "task-prod-f1": {
            "missing_product_rule_term": 2*x * sympy.sin(x),
            "wrong_derivative_sin": 2*x * sympy.sin(x) + x**2 * sympy.sin(x),
            "wrong_derivative_power": x * sympy.sin(x) + x**2 * sympy.cos(x),
            "unknown_error": sympy.Integer(42),
        },
    }
    for case in cases_from_tasks(TASKS_DIR):
        reference = case.evaluation_only.reference
        derivative = str(sympy.diff(instances[case.task_instance_id], x))
        for formula in [reference.final_answer] + reference.equivalent_forms:
            equivalent, reason = symbolic_equivalence(formula, derivative)
            assert equivalent is True, (case.case_id, reason)
        equivalent, reason = symbolic_equivalence(case.tutor_context.student_answer, derivative)
        if reference.expected_input_validity == "invalid":
            assert equivalent is None, (case.case_id, reason)
        else:
            assert equivalent is (reference.expected_correctness == "correct"), (case.case_id, reason)
            if reference.expected_diagnosis is not None:
                expected = error_answers[case.task_instance_id][reference.expected_diagnosis]
                equivalent, reason = symbolic_equivalence(case.tutor_context.student_answer, str(expected))
                assert equivalent is True, (case.case_id, reason)
        assert case.evaluation_only.verification.mathematics_status == "pending"
        assert case.evaluation_only.verification.diagnosis_status == "pending"
