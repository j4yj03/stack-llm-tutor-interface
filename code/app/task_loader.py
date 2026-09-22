import json
from pathlib import Path
from typing import Dict

from jsonschema import Draft202012Validator

from app.config import (
    MAX_CONTEXT_QUESTION_TEXT,
    MAX_QUESTION_TEXT_LENGTH,
    SCHEMA_PATH,
    TASK_DIR
)


def load_json(path: Path) -> Dict:
    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def load_schema() -> Dict:
    if not SCHEMA_PATH.exists():
        raise RuntimeError(
            f"JSON-Schema nicht gefunden: {SCHEMA_PATH}"
        )

    return load_json(SCHEMA_PATH)


def validate_task(
    task: Dict,
    schema: Dict,
    path: Path
) -> None:
    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(task),
        key=lambda error: list(error.path)
    )

    if not errors:
        return

    messages = []

    for error in errors:
        location = ".".join(
            str(part)
            for part in error.path
        )

        if not location:
            location = "<root>"

        messages.append(
            f"{location}: {error.message}"
        )

    raise RuntimeError(
        f"Ungültige Aufgabe in {path}:\n"
        + "\n".join(messages)
    )


def validate_template(
    task: Dict,
    path: Path
) -> None:
    """Das optionale Textbaustein-Feld muss den {funktion}-Platzhalter
    enthalten und muss zusammen mit der übertragenen Funktion in das
    Kontextlimit passen."""

    template = task.get("question_text_template")

    if template is None:
        return

    if "{funktion}" not in template:
        raise RuntimeError(
            f"question_text_template in {path} muss "
            "den Platzhalter {funktion} enthalten"
        )

    if len(template) + MAX_QUESTION_TEXT_LENGTH > MAX_CONTEXT_QUESTION_TEXT:
        raise RuntimeError(
            f"question_text_template in {path} ist zu lang: "
            f"maximal {MAX_CONTEXT_QUESTION_TEXT - MAX_QUESTION_TEXT_LENGTH} "
            "Zeichen, damit Textbaustein und übertragene Funktion zusammen "
            "in den gespeicherten Aufgabentext passen"
        )


def load_all_tasks() -> Dict[str, Dict]:
    if not TASK_DIR.exists():
        raise RuntimeError(
            f"Aufgabenordner nicht gefunden: {TASK_DIR}"
        )

    schema = load_schema()
    tasks: Dict[str, Dict] = {}

    for path in sorted(TASK_DIR.glob("*.json")):
        task = load_json(path)
        validate_task(task, schema, path)
        validate_template(task, path)

        question_id = task["question_id"]

        if question_id in tasks:
            raise RuntimeError(
                "Doppelte question_id gefunden: "
                f"{question_id}"
            )

        tasks[question_id] = task

    if not tasks:
        raise RuntimeError(
            f"Keine Aufgaben in {TASK_DIR} gefunden"
        )

    return tasks