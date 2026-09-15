from fastapi.testclient import TestClient

import app.main as main_module
from app.llm import (
    LLMError,
    LLMRateLimitError
)


def test_health():
    client = TestClient(main_module.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


class FakeLLMClient:
    def __init__(self, answer="Welche Funktion steht im Exponenten?"):
        self.answer = answer

    def chat(
        self,
        messages,
        model=None,
        temperature=0.2,
        max_tokens=400,
        json_output=False
    ):
        if isinstance(self.answer, Exception):
            raise self.answer

        return self.answer


class StartPayload:
    @staticmethod
    def body():
        return {
            "stack": {
                "question_id": "chain_rule_001",
                "question_text": (
                    "Differenzieren Sie f(x)."
                ),
                "student_answer": "-5",
                "diagnosis_code": "unknown_error"
            },
            "hint_level": 1
        }


def test_start_tutor_with_mocked_llm(
    monkeypatch
):
    monkeypatch.setattr(
        main_module,
        "create_llm_client",
        lambda: FakeLLMClient()
    )

    response = TestClient(
        main_module.app
    ).post(
        "/api/tutor/start",
        json=StartPayload.body()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["hint_level"] == 1
    assert data["hint"] == (
        "Welche Funktion steht im Exponenten?"
    )
    assert data["chat_id"]


def test_rate_limit_returns_429(
    monkeypatch
):
    monkeypatch.setattr(
        main_module,
        "create_llm_client",
        lambda: FakeLLMClient(
            answer=LLMRateLimitError(
                "Retry-After=36"
            )
        )
    )

    response = TestClient(
        main_module.app
    ).post(
        "/api/tutor/start",
        json=StartPayload.body()
    )

    assert response.status_code == 429
    assert "Rate-Limit" in response.json()[
        "detail"
    ]


def test_llm_error_returns_502(
    monkeypatch
):
    monkeypatch.setattr(
        main_module,
        "create_llm_client",
        lambda: FakeLLMClient(
            answer=LLMError("Verbindung fehlgeschlagen")
        )
    )

    response = TestClient(
        main_module.app
    ).post(
        "/api/tutor/start",
        json=StartPayload.body()
    )

    assert response.status_code == 502
