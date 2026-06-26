import json
from pathlib import Path
from jsonschema import Draft202012Validator


BASE_DIR = Path(__file__).resolve().parent.parent
TASK_DIR = BASE_DIR / "tasks"
SCHEMA_PATH = BASE_DIR / "schemas" / "stack_ai_tutor_task.schema.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_schema() -> dict:
    return load_json(SCHEMA_PATH)


def validate_task(task: dict, schema: dict, path: Path) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(task), key=lambda e: e.path)

    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(p) for p in error.path)
            if not location:
                location = "<root>"
            messages.append(f"{location}: {error.message}")

        message = "\n".join(messages)
        raise RuntimeError(f"Ungültige Aufgabe in {path}:\n{message}")


def load_all_tasks() -> dict:
    schema = load_schema()
    tasks = {}

    for path in TASK_DIR.glob("*.json"):
        task = load_json(path)
        validate_task(task, schema, path)

        qid = task["question_id"]

        if qid in tasks:
            raise RuntimeError(f"Doppelte question_id gefunden: {qid}")

        tasks[qid] = task

    if not tasks:
        raise RuntimeError(f"Keine Aufgaben in {TASK_DIR} gefunden.")

    return tasks