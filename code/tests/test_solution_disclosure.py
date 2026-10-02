import pytest

from app.schemas import ContextOptions
from app.main import TASKS, task_to_stack_context


def prompt_text(messages) -> str:
    return "\n".join(
        message["content"]
        for message in messages
    )


@pytest.mark.parametrize(
    "hint_level",
    [0, 1, 2, 3]
)
def test_final_answer_is_hidden_before_level_four(
    prompt_builder,
    stack_context,
    hint_level
):
    options = ContextOptions(
        include_solution_steps=True,
        include_final_answer=True
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=hint_level,
        options=options,
        history=[]
    )

    text = prompt_text(messages)

    assert stack_context.final_answer not in text


def test_final_answer_is_available_at_level_four(
    prompt_builder,
    stack_context
):
    options = ContextOptions(
        include_final_answer=True
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=4,
        options=options,
        history=[]
    )

    text = prompt_text(messages)

    assert stack_context.final_answer in text


def test_solution_steps_are_hidden_at_level_one(
    prompt_builder,
    stack_context
):
    options = ContextOptions(
        include_solution_steps=True,
        # Hermetisch: Lernziel-Defaults können textuell mit Lösungsschritten
        # kollidieren; dieser Test prüft ausschließlich die Schritte.
        include_learning_goals=False
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=1,
        options=options,
        history=[]
    )

    text = prompt_text(messages)

    for step in stack_context.solution_steps:
        assert step not in text


def test_level_one_contains_solution_prohibition(
    prompt_builder,
    stack_context
):
    options = ContextOptions()

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=1,
        options=options,
        history=[]
    )

    system_prompt = messages[0]["content"]

    assert "Endergebnis" in system_prompt
    assert "vollständige Rechnung" in system_prompt


@pytest.mark.parametrize("task", TASKS.values(), ids=TASKS.keys())
@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_real_tasks_do_not_leak_final_answer_via_solution_steps(prompt_builder, task, level):
    stack = task_to_stack_context(task, "0", "unknown_error")
    messages = prompt_builder.build_messages(
        stack=stack, hint_level=level,
        options=ContextOptions(include_solution_steps=True, include_final_answer=True),
        history=[]
    )
    text = prompt_text(messages)
    assert (stack.final_answer in text) == (level == 4)
    if level == 3:
        for step in stack.solution_steps[3:]:
            assert step not in text


@pytest.mark.parametrize("level", [3, 4])
def test_final_answer_disabled_also_filters_answer_in_steps(prompt_builder, stack_context, level):
    stack_context.solution_steps = [
        "Innere Funktion bestimmen",
        "Endergebnis: " + stack_context.final_answer,
        "Ein weiterer Schritt nach der Lösung"
    ]
    messages = prompt_builder.build_messages(
        stack=stack_context, hint_level=level,
        options=ContextOptions(include_solution_steps=True, include_final_answer=False),
        history=[]
    )
    text = prompt_text(messages)
    assert stack_context.solution_steps[0] in text
    assert stack_context.final_answer not in text
    assert stack_context.solution_steps[2] not in text


@pytest.mark.parametrize("mode", ["tutor", "general"])
@pytest.mark.parametrize("steps,final", [(False, False), (False, True), (True, False)])
def test_context_permissions_remain_required_at_full_support(
    prompt_builder, stack_context, monkeypatch, mode, steps, final
):
    from app import config

    monkeypatch.setattr(config, "TUTOR_POLICY_MODE", mode)
    messages = prompt_builder.build_messages(
        stack=stack_context, hint_level=4,
        options=ContextOptions(
            include_solution_steps=steps, include_final_answer=final, include_learning_goals=False
        ), history=[]
    )
    context = messages[-1]["content"]
    assert (stack_context.final_answer in context) == final
    for step in stack_context.solution_steps:
        assert (step in context) == steps


def test_stage_zero_still_needs_policy_permission_when_context_cap_allows_references(
    prompt_builder, stack_context, monkeypatch
):
    from app import config

    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        "question_text,student_answer,solution_steps,final_answer"
    ))
    messages = prompt_builder.build_messages(
        stack=stack_context, hint_level=0,
        options=ContextOptions(include_solution_steps=True, include_final_answer=True), history=[]
    )
    context = messages[-1]["content"]
    assert stack_context.final_answer not in context
    for step in stack_context.solution_steps:
        assert step not in context
