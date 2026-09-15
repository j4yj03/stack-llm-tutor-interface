import pytest

import app.config as config
from app.llm import (
    LLMError,
    OllamaNativeClient,
    SAIClient,
    create_llm_client
)
from app.ollama_client import (
    OllamaClientError,
    call_ollama_chat
)


class FakeLLMClient:
    def __init__(self):
        self.calls = []

    def chat(
        self,
        messages,
        model=None,
        temperature=0.2,
        max_tokens=400,
        json_output=False
    ):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_output": json_output
            }
        )
        return "Fiktiver Hinweis"


def test_factory_selects_saia():
    client = create_llm_client("saia")

    assert isinstance(client, SAIClient)


def test_factory_selects_ollama():
    client = create_llm_client("ollama")

    assert isinstance(client, OllamaNativeClient)


def test_factory_litellm_alias_maps_to_saia():
    client = create_llm_client("litellm")

    assert isinstance(client, SAIClient)


def test_factory_uses_configured_mode(
    monkeypatch
):
    monkeypatch.setattr(
        config,
        "LLM_API_MODE",
        "ollama"
    )

    assert isinstance(
        create_llm_client(),
        OllamaNativeClient
    )


def test_factory_rejects_unknown_mode():
    with pytest.raises(LLMError):
        create_llm_client("huggingface")


def test_compat_wrapper_delegates(
    monkeypatch
):
    fake = FakeLLMClient()

    monkeypatch.setattr(
        "app.ollama_client.create_llm_client",
        lambda: fake
    )

    answer = call_ollama_chat(
        messages=[
            {"role": "user", "content": "Test"}
        ],
        model="qwen3-32b",
        temperature=0.1,
        max_tokens=50
    )

    assert answer == "Fiktiver Hinweis"
    assert fake.calls[0]["model"] == "qwen3-32b"
    assert fake.calls[0]["temperature"] == 0.1
    assert fake.calls[0]["max_tokens"] == 50


def test_compat_wrapper_error_alias():
    assert OllamaClientError is LLMError
