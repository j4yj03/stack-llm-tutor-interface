from pathlib import Path

import pytest

from app.config import (
    MAX_CONTEXT_QUESTION_TEXT,
    MAX_QUESTION_TEXT_LENGTH
)
from app.task_loader import load_all_tasks, validate_template


def test_template_without_placeholder_is_rejected():
    with pytest.raises(RuntimeError, match=r"\{funktion\}"):
        validate_template(
            {"question_text_template": "Gegeben ist die Funktion."},
            Path("tasks/beispiel.json")
        )


def test_template_must_leave_room_for_the_function():
    # Konfigurationsunabhängig: Das Deployment-Limit (hier 500) bestimmt,
    # wie viel Raum der Textbaustein dem übertragenen Funktionstext lässt.
    limit = MAX_CONTEXT_QUESTION_TEXT - MAX_QUESTION_TEXT_LENGTH
    assert limit >= 0

    template = "x" * (limit + 1) + " {funktion}"
    with pytest.raises(RuntimeError, match="zu lang"):
        validate_template(
            {"question_text_template": template},
            Path("tasks/beispiel.json")
        )


def test_task_without_template_is_accepted():
    validate_template({}, Path("tasks/beispiel.json"))


def test_real_tasks_are_generic_and_templated():
    tasks = load_all_tasks()

    for task in tasks.values():
        template = task["question_text_template"]

        assert "{funktion}" in template
        assert task["question_text"] != template

        # Data that can reach the LLM for a Moodle variant must not contain
        # fixed example values of the local variant.
        texts = [task["question_text"], template, *task["learning_goals"]]
        for diagnosis in task["diagnoses"].values():
            texts.append(diagnosis["title"])
            texts.append(diagnosis["description"])

        for text in texts:
            assert "-5e^(x^2-2e^x)" not in text
            assert "x^2-2e^x" not in text
            assert "-2e^x" not in text
            assert "x^2 und sin(x)" not in text
            assert "Ableitung von sin(x)" not in text

        # The concrete function always comes from Moodle/STACK.
        assert "function" not in task.get("given_data", {})
