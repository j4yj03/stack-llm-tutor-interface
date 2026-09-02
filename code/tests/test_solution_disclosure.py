import pytest

from app.schemas import ContextOptions


def prompt_text(messages) -> str:
    return "\n".join(
        message["content"]
        for message in messages
    )


@pytest.mark.parametrize(
    "hint_level",
    [1, 2, 3]
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
        include_solution_steps=True
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