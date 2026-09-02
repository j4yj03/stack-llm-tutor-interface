from fastapi.testclient import TestClient

import app.main as main_module


def test_health():
    client = TestClient(main_module.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_start_tutor_with_mocked_llm(
    monkeypatch,
    tmp_path
):
    def fake_call_ollama_chat(
        messages,
        model=None,
        temperature=0.2,
        max_tokens=400
    ):
        return "Welche Funktion steht im Exponenten?"

    monkeypatch.setattr(
        main_module,
        "call_ollama_chat",
        fake_call_ollama_chat
    )

    response = TestClient(main_module.app).post(
        "/api/tutor/start",
        json={
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
    )

    assert response.status_code == 200

    data = response.json()

    assert data["hint_level"] == 1
    assert data["hint"] == (
        "Welche Funktion steht im Exponenten?"
    )
    assert data["chat_id"]