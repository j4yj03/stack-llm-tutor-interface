import pytest

import app.config as config
import app.llm._http as http_module
from app.llm import (
    LLMResponseError,
    OllamaNativeClient
)


MESSAGES = [
    {"role": "user", "content": "Gib einen Hinweis."}
]

OLLAMA_URL = (
    config.LLM_BASE_URL.rstrip("/")
    + "/api/chat"
)


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        json_data=None,
        text=""
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = {}

    def json(self):
        if self._json is None:
            raise ValueError("Keine JSON-Daten")

        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(
                f"HTTP {self.status_code}",
                response=self
            )


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "verify": verify
            }
        )
        return self.response


def test_ollama_happy_path(monkeypatch):
    session = FakeSession(
        FakeResponse(
            json_data={
                "message": {
                    "role": "assistant",
                    "content": "  Hinweis  "
                }
            }
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    answer = OllamaNativeClient().chat(
        messages=MESSAGES,
        model="qwen3:8b",
        temperature=0.3,
        max_tokens=50
    )

    assert answer == "Hinweis"

    call = session.calls[0]

    assert call["url"] == OLLAMA_URL
    assert call["verify"] is True
    assert call["json"]["model"] == "qwen3:8b"
    assert call["json"]["think"] is False
    assert call["json"]["stream"] is False
    assert call["json"]["options"][
        "temperature"
    ] == 0.3
    assert call["json"]["options"][
        "num_predict"
    ] == 50


def test_ollama_empty_content(monkeypatch):
    session = FakeSession(
        FakeResponse(
            json_data={
                "message": {"content": "  "}
            }
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMResponseError):
        OllamaNativeClient().chat(
            messages=MESSAGES
        )


def test_ollama_missing_message(monkeypatch):
    session = FakeSession(
        FakeResponse(json_data={})
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMResponseError):
        OllamaNativeClient().chat(
            messages=MESSAGES
        )
