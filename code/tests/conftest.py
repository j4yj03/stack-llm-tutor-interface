import json
from pathlib import Path

import pytest

from app.chat_store import ChatStore
from app.database import initialize_database
from app.hint_policy import HintPolicy
from app.prompt_builder import PromptBuilder
from app.schemas import StackContext


@pytest.fixture
def hint_policy_path(tmp_path: Path) -> Path:
    source = Path("config/hint_levels.json")
    target = tmp_path / "hint_levels.json"
    target.write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8"
    )
    return target


@pytest.fixture
def hint_policy(
    hint_policy_path: Path
) -> HintPolicy:
    return HintPolicy(hint_policy_path)


@pytest.fixture
def prompt_builder(
    hint_policy: HintPolicy
) -> PromptBuilder:
    return PromptBuilder(hint_policy)


@pytest.fixture
def stack_context() -> StackContext:
    return StackContext(
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
        score=0.0,
        learning_goals=[
            "Kettenregel anwenden"
        ],
        math_rules=[
            "Für exp(g(x)) gilt "
            "exp(g(x))*g'(x)."
        ],
        solution_steps=[
            "Innere Funktion bestimmen",
            "Innere Funktion ableiten",
            "Kettenregel anwenden"
        ],
        final_answer=(
            "-5*exp(x^2-2*exp(x))"
            "*(2*x-2*exp(x))"
        )
    )


@pytest.fixture
def chat_store(tmp_path: Path) -> ChatStore:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)
    return ChatStore(database_path)