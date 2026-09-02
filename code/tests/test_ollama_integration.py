import pytest

from app.config import OLLAMA_MODEL
from app.ollama_client import (
    call_ollama_chat
)


@pytest.mark.integration
def test_ollama_chat_connection():
    messages = [
        {
            "role": "system",
            "content": (
                "Du bist ein Mathematik-Tutor. "
                "Gib keine vollständige Lösung aus."
            )
        },
        {
            "role": "user",
            "content": (
                "Die innere Ableitung wurde "
                "vergessen. Gib einen kurzen Hinweis."
            )
        }
    ]

    answer = call_ollama_chat(
        messages=messages,
        model=OLLAMA_MODEL,
        temperature=0.0,
        max_tokens=150
    )

    assert isinstance(answer, str)
    assert answer.strip()