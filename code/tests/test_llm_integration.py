import pytest

from app import config
from app.ollama_client import call_ollama_chat


requires_api_key = pytest.mark.skipif(
    config.LLM_API_MODE not in ("ollama",)
    and not config.LLM_API_KEY,
    reason=(
        "Kein API-Key gesetzt (LLM_API_KEY) - "
        "Integrationstest übersprungen"
    )
)


@pytest.mark.integration
@requires_api_key
def test_llm_chat_connection():
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
        model=config.LLM_MODEL,
        temperature=0.0,
        max_tokens=150
    )

    assert isinstance(answer, str)
    assert answer.strip()
