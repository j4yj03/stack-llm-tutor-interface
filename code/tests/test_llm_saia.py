import pytest
import requests

import app.config as config
import app.llm._http as http_module
from app.llm import (
    LLMAuthError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError
)
from app.llm.saia import SAIClient


MESSAGES = [
    {"role": "system", "content": "Du bist ein Tutor."},
    {"role": "user", "content": "Gib einen Hinweis."}
]

SAIA_URL = (
    config.LLM_BASE_URL.rstrip("/")
    + "/chat/completions"
)


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        json_data=None,
        text="",
        headers=None
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("Keine JSON-Daten")

        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
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
                "headers": headers,
                "timeout": timeout,
                "verify": verify
            }
        )
        return self.response


@pytest.fixture
def saia_key(monkeypatch):
    monkeypatch.setattr(
        config,
        "LLM_API_KEY",
        "test-key-123"
    )


def _client_response():
    return FakeResponse(
        json_data={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "  Hinweis: Kettenregel.  "
                    },
                    "finish_reason": "stop"
                }
            ]
        }
    )


def test_saia_happy_path(
    monkeypatch,
    saia_key
):
    session = FakeSession(_client_response())
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    answer = SAIClient().chat(
        messages=MESSAGES,
        model="qwen3-32b",
        temperature=0.1,
        max_tokens=99
    )

    assert answer == "Hinweis: Kettenregel."

    call = session.calls[0]

    assert call["url"] == SAIA_URL
    assert call["verify"] is True
    assert call["headers"][
        "Authorization"
    ] == "Bearer test-key-123"
    assert call["json"]["model"] == "qwen3-32b"
    assert call["json"]["messages"] == MESSAGES
    assert call["json"]["stream"] is False
    assert call["json"]["temperature"] == 0.1
    assert call["json"]["max_tokens"] == 99
    assert call["json"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }


def test_saia_thinking_allowed_via_config(
    monkeypatch,
    saia_key
):
    monkeypatch.setattr(
        config,
        "LLM_DISABLE_THINKING",
        False
    )
    session = FakeSession(_client_response())
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    SAIClient().chat(messages=MESSAGES)

    assert (
        "chat_template_kwargs"
        not in session.calls[0]["json"]
    )


def test_saia_missing_key_raises_auth(
    monkeypatch
):
    monkeypatch.setattr(
        config,
        "LLM_API_KEY",
        ""
    )

    with pytest.raises(LLMAuthError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_http_401_maps_to_auth_error(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(
            status_code=401,
            json_data={"error": "unauthorized"},
            text="unauthorized"
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMAuthError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_http_429_maps_to_rate_limit(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(
            status_code=429,
            json_data={"error": "rate limited"},
            text="rate limited",
            headers={"Retry-After": "36"}
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMRateLimitError) as excinfo:
        SAIClient().chat(messages=MESSAGES)

    assert "Retry-After=36" in str(excinfo.value)


def test_saia_http_500_maps_to_connection_error(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(
            status_code=500,
            json_data={"error": "boom"},
            text="boom"
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMConnectionError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_empty_content_raises_response_error(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(
            json_data={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "   "
                        },
                        "finish_reason": "length"
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMResponseError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_missing_choices_raises_response_error(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(json_data={})
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMResponseError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_invalid_json_raises_response_error(
    monkeypatch,
    saia_key
):
    session = FakeSession(
        FakeResponse(text="<html>oops</html>")
    )
    monkeypatch.setattr(
        http_module,
        "SESSION",
        session
    )

    with pytest.raises(LLMResponseError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_connection_error_mapping(
    monkeypatch,
    saia_key
):
    class BrokenSession:
        def post(self, url, **kwargs):
            raise requests.exceptions.ConnectionError(
                "refused"
            )

    monkeypatch.setattr(
        http_module,
        "SESSION",
        BrokenSession()
    )

    with pytest.raises(LLMConnectionError):
        SAIClient().chat(messages=MESSAGES)


def test_saia_timeout_mapping(
    monkeypatch,
    saia_key
):
    class SlowSession:
        def post(self, url, **kwargs):
            raise requests.exceptions.Timeout()

    monkeypatch.setattr(
        http_module,
        "SESSION",
        SlowSession()
    )

    with pytest.raises(LLMConnectionError):
        SAIClient().chat(messages=MESSAGES)
