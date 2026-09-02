import pytest

from app.ollama_client import call_ollama_chat
from app.prompt_builder import PromptBuilder
from app.hint_policy import HintPolicy
from app.schemas import (
    ContextOptions,
    StackContext
)


@pytest.mark.integration
def test_level_one_does_not_reveal_final_answer():
    stack = StackContext(
        question_id="chain_rule_001",
        question_text=(
            "Differenzieren Sie "
            "f(x)=-5e^(x^2-2e^x)."
        ),
        student_answer=(
            "-5*exp(x^2-2*exp(x))"
        ),
        diagnosis_code=(
            "missing_inner_derivative"
        ),
        prt_feedback=(
            "Die innere Ableitung fehlt."
        ),
        final_answer=(
            "-5*exp(x^2-2*exp(x))"
            "*(2*x-2*exp(x))"
        )
    )

    builder = PromptBuilder(HintPolicy())

    messages = builder.build_messages(
        stack=stack,
        hint_level=1,
        options=ContextOptions(
            include_final_answer=False,
            include_solution_steps=False
        ),
        history=[]
    )

    answer = call_ollama_chat(
        messages=messages,
        model="qwen3.6:27b",
        temperature=0.0,
        max_tokens=150
    )

    forbidden_fragments = [
        "2*x-2*exp(x)",
        "2x-2e^x",
        "-5e^(x^2-2e^x)(2x-2e^x)"
    ]

    normalized = answer.replace(" ", "").lower()

    for fragment in forbidden_fragments:
        assert (
            fragment.replace(" ", "").lower()
            not in normalized
        )