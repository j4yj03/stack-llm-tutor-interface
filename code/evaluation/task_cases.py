"""Offline task-derived synthetic cases, never STACK/PRT evidence.

Each evaluation_examples function explicitly names the fixed instance of the
task's model_solution. No function or error is inferred from an answer.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import (
    SchemaError,
    ValidationError as SchemaValidationError,
)
from pydantic import ValidationError

from evaluation.corpus import CorpusError, sha256_file
from evaluation.models import Case, SCHEMA_VERSION

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas" / "stack_ai_tutor_task.schema.json"
)


def _validated_tasks(
    tasks_dir: Path, schema_path: Optional[Path] = None
) -> List[Tuple[Path, dict]]:
    if not tasks_dir.is_dir():
        raise CorpusError("Task directory not found: " + str(tasks_dir))
    paths = sorted(tasks_dir.glob("*.json"))
    if not paths:
        raise CorpusError("No task JSON files found in " + str(tasks_dir))
    schema_path = DEFAULT_SCHEMA_PATH if schema_path is None else schema_path
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as error:
        raise CorpusError(
            "Invalid task schema " + str(schema_path) + ": " + str(error)
        ) from error
    validator = Draft202012Validator(schema)
    tasks: List[Tuple[Path, dict]] = []
    question_ids = set()
    for path in paths:
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            validator.validate(task)
        except SchemaValidationError as error:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            raise CorpusError(
                "Invalid task " + str(path) + " at " + location + ": " + error.message
            ) from error
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CorpusError(
                "Invalid task JSON " + str(path) + ": " + str(error)
            ) from error
        question_id = task["question_id"]
        if question_id in question_ids:
            raise CorpusError("Duplicate question_id in " + str(path) + ": " + question_id)
        question_ids.add(question_id)
        template = task.get("question_text_template")
        if template is not None and "{funktion}" not in template:
            raise CorpusError(
                "question_text_template in " + str(path)
                + " must contain {funktion}"
            )
        tasks.append((path, task))
    return tasks


def cases_from_tasks(
    tasks_dir: Path, schema_path: Optional[Path] = None
) -> List[Case]:
    """Validate all tasks and derive cases only from explicit examples.

    Valid tasks without evaluation_examples contribute no cases. Supplied error
    keys and titles are synthetic context; absent keys stay absent. References
    remain evaluation-only until a context profile explicitly requests them.
    """
    cases: List[Case] = []
    case_ids = set()
    instance_ids = set()
    for path, task in _validated_tasks(tasks_dir, schema_path):
        examples = task.get("evaluation_examples")
        if examples is None:
            continue
        instance_id = examples["instance_id"]
        if instance_id in instance_ids:
            raise CorpusError("Duplicate instance_id in " + str(path) + ": " + instance_id)
        instance_ids.add(instance_id)
        template = task.get("question_text_template")
        if template is None:
            raise CorpusError(
                "evaluation_examples in " + str(path)
                + " require question_text_template"
            )
        question_text = template.replace("{funktion}", examples["function"])
        solution = task["model_solution"]
        steps = [
            step["description"] + (" Formel: " + step["formula"] if step.get("formula") else "")
            for step in solution["solution_steps"]
            if step["description"] or step.get("formula")
        ]
        for answer in examples["answers"]:
            case_id = answer["case_id"]
            if case_id in case_ids:
                raise CorpusError("Duplicate case_id in " + str(path) + ": " + case_id)
            case_ids.add(case_id)
            error_key = answer.get("expected_error")
            if error_key is not None and error_key not in task["diagnoses"]:
                raise CorpusError(
                    "Unknown expected_error " + repr(error_key)
                    + " for " + case_id + " in " + str(path)
                )
            feedback = None
            if error_key is not None:
                feedback = (
                    "Synthetischer Fehlerkontext (keine STACK/PRT-Pruefung): "
                    + task["diagnoses"][error_key]["title"]
                )
            try:
                case = Case(
                    schema_version=SCHEMA_VERSION,
                    case_id=case_id,
                    readiness="draft",
                    tags=["task_derived", "synthetic"],
                    task_instance_id=instance_id,
                    tutor_context={
                        "question_id": task["question_id"],
                        "question_text": question_text,
                        "student_answer": answer["student_answer"],
                        "diagnosis_code": error_key,
                        "prt_feedback": feedback,
                        "score": None,
                        "seed": None,
                        "learning_goals": task["learning_goals"],
                        "math_rules": [],
                        "solution_steps": [],
                        "final_answer": None,
                    },
                    evaluation_only={
                        "instance": {
                            "instance_id": instance_id,
                            "seed": None,
                            "variable": task.get("given_data", {}).get("variable", "x"),
                        },
                        "reference": {
                            "expected_input_validity": answer["expected_input_validity"],
                            "expected_correctness": answer["expected_correctness"],
                            "expected_diagnosis": error_key,
                            "final_answer": solution["final_answer"],
                            "equivalent_forms": solution.get("equivalent_forms", []),
                            "solution_steps": steps,
                        },
                        "verification": {
                            "mathematics_status": "pending",
                            "diagnosis_status": "pending",
                        },
                        "provenance": {
                            "response_origin": "synthetic_fixture",
                            "instantiated_task_ref": "tasks/" + path.name + "#evaluation_examples",
                        },
                    },
                )
            except ValidationError as error:
                raise CorpusError(
                    "Invalid case " + case_id + " from " + str(path)
                    + ": " + str(error)
                ) from error
            cases.append(case)
    return cases


def task_source_hashes(
    tasks_dir: Path, schema_path: Optional[Path] = None
) -> Dict[str, str]:
    """SHA-256 of every validated task, keyed by its task-relative source ref."""
    return {
        "tasks/" + path.name: sha256_file(path)
        for path, _task in _validated_tasks(tasks_dir, schema_path)
    }


def write_task_cases(
    cases: List[Case], output_path: Path, overwrite: bool = False
) -> None:
    """Write current-schema JSONL to an existing parent directory.

    Validate and serialize the complete bank before opening the output. An
    existing file is never replaced unless overwrite is explicitly enabled.
    """
    records = []
    case_ids = set()
    for case in cases:
        try:
            record = Case.model_validate(case.model_dump()).model_dump(mode="json")
        except ValidationError as error:
            raise CorpusError("Invalid task-derived case: " + str(error)) from error
        if record["case_id"] in case_ids:
            raise CorpusError("Duplicate case_id in output: " + record["case_id"])
        case_ids.add(record["case_id"])
        records.append(record)
    if not records:
        raise CorpusError("No evaluation examples to write")
    payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    with output_path.open(
        "w" if overwrite else "x", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(payload)
