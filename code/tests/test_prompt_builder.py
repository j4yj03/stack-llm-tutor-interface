from app.schemas import ContextOptions


def combine_messages(messages) -> str:
    return "\n".join(
        message["content"]
        for message in messages
    )


def test_minimal_context(
    prompt_builder,
    stack_context
):
    options = ContextOptions(
        include_question_text=True,
        include_student_answer=True,
        include_diagnosis_code=False,
        include_prt_feedback=False,
        include_score=False,
        include_learning_goals=False,
        include_math_rules=False,
        include_solution_steps=False,
        include_final_answer=False,
        include_chat_history=False
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=1,
        options=options,
        history=[]
    )

    text = combine_messages(messages)

    assert stack_context.question_text in text
    assert stack_context.student_answer in text
    assert "missing_inner_derivative" not in text
    assert "Die innere Ableitung fehlt" not in text
    assert stack_context.final_answer not in text


def test_diagnosis_can_be_enabled(
    prompt_builder,
    stack_context
):
    options = ContextOptions(
        include_diagnosis_code=True,
        include_prt_feedback=True
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=1,
        options=options,
        history=[]
    )

    text = combine_messages(messages)

    assert "missing_inner_derivative" in text
    assert "Die innere Ableitung fehlt" in text


def test_chat_history_can_be_disabled(
    prompt_builder,
    stack_context
):
    history = [
        {
            "role": "user",
            "content": "Was ist die innere Funktion?"
        }
    ]

    options = ContextOptions(
        include_chat_history=False
    )

    messages = prompt_builder.build_messages(
        stack=stack_context,
        hint_level=1,
        options=options,
        history=history
    )

    text = combine_messages(messages)

    assert "Was ist die innere Funktion?" not in text