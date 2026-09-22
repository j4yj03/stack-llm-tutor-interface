import json
from copy import deepcopy
from html.parser import HTMLParser
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

import app.main as main_module
from app.database import initialize_database
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
        self.calls = []

    def chat(
        self,
        messages,
        model=None,
        temperature=0.2,
        max_tokens=400,
        json_output=False
    ):
        self.calls.append({
            "messages": deepcopy(messages),
            "model": model
        })
        if isinstance(self.answer, Exception):
            raise self.answer

        return self.answer


@pytest.fixture(autouse=True)
def isolated_api_store(monkeypatch, chat_store):
    monkeypatch.setattr(main_module, "CHAT_STORE", chat_store)
    monkeypatch.setattr(
        main_module, "initialize_database",
        lambda: initialize_database(chat_store.database_path)
    )


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLMClient()
    monkeypatch.setattr(main_module, "create_llm_client", lambda: fake)
    return fake


@pytest.fixture
def client():
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.fixture
def start_params():
    return {
        "qid": "ableitung_kettenregel_exp_001",
        "diagnosis": "missing_chain_rule_inner_derivative",
        "ans1": "-5*exp(x^2-2*exp(x))",
        "hint_level": 1
    }


def read_form(response, form_id):
    class FormParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.action = None
            self.fields = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                self.active = attrs.get("id") == form_id
                if self.active:
                    self.action = attrs["action"]
            if self.active and tag == "input" and "name" in attrs:
                self.fields[attrs["name"]] = attrs.get("value", "")

        def handle_endtag(self, tag):
            if tag == "form":
                self.active = False

    parser = FormParser()
    parser.feed(response.text)
    assert parser.action is not None
    return parser.action, parser.fields


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


def test_start_page_renders_html(
    monkeypatch
):
    monkeypatch.setattr(
        main_module,
        "create_llm_client",
        lambda: FakeLLMClient()
    )

    question_id = next(
        iter(main_module.TASKS)
    )
    task = main_module.TASKS[question_id]
    diagnosis = next(
        iter(task["diagnoses"])
    )

    response = TestClient(
        main_module.app
    ).get(
        "/start",
        params={
            "qid": question_id,
            "diagnosis": diagnosis,
            "ans1": "-5",
            "hint_level": 1
        }
    )

    assert response.status_code == 200
    assert response.headers[
        "content-type"
    ].startswith("text/html")
    assert "AI Tutor" in response.text
    assert question_id in response.text
    assert diagnosis in response.text
    assert (
        "Welche Funktion steht im Exponenten?"
        in response.text
    )


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


def test_start_renders_actual_prompt_and_script_free_forms(client, llm, start_params):
    response = client.get("/start", params=start_params)

    assert response.status_code == 200
    prompt = response.context["prompt"]
    assert json.loads(prompt) == llm.calls[-1]["messages"]
    assert str(escape(prompt)) in response.text
    assert '<pre id="debug-prompt">' in response.text
    assert '<textarea id="message" name="message"' in response.text
    assert '<script' not in response.text.lower()
    assert 'name="chat_id"' in response.text
    assert llm.answer not in prompt  # The response was not yet part of the input.
    assert "<student_answer>" in prompt.replace("\\n", "\n")

    options = json.loads(response.context["context_options"])
    assert options == main_module.model_dump_compat(
        main_module.ContextOptions(
            include_learning_goals=True,
            include_solution_steps=True,
            include_final_answer=True
        )
    )
    assert '<pre id="debug-context-options">' in response.text
    assert "Aufgabenvariante" not in response.text
    assert "is_moodle_variant" not in response.context
    assert response.context["chat_messages"] == list(
        reversed(response.context["history"])
    )


def test_moodle_context_survives_html_chat_and_next_hint(client, llm, start_params):
    question = "Differenzieren Sie f(x)=7*%e^(x^3-3*%e^x). Bedingung: x>0 & x<5."
    start_params.update({
        "question_text": "  " + question + "  ",
        "ans1": "7*%e^(x^3-3*%e^x)+1",
        "model": main_module.LLM_MODEL
    })
    initial = client.get("/start", params=start_params)
    assert initial.status_code == 200
    chat_id = initial.context["chat_id"]
    assert initial.context["question_text"] == question
    stack = main_module.CHAT_STORE.get_chat(chat_id)["stack_context"]
    assert stack["question_text"] == question
    assert stack["student_answer"] == start_params["ans1"]

    action, fields = read_form(initial, "chat-form")
    fields["message"] = "Warum brauche ich die innere Ableitung?"
    llm.answer = "Vergleiche die äußere Funktion mit ihrem Exponenten."
    reply = client.post(action, data=fields)
    assert reply.status_code == 200
    assert reply.context["chat_id"] == chat_id
    assert reply.context["question_text"] == question
    assert reply.context["hint_level"] == 1
    assert reply.context["model"] == start_params["model"]
    assert reply.context["context_options"] == (
        initial.context["context_options"]
    )
    # Chat-Panel: neueste Beiträge zuerst (CSS-Anker am neuesten Beitrag).
    chat_messages = reply.context["chat_messages"]
    assert chat_messages[0]["content"] == llm.answer
    assert chat_messages[-1]["content"] == "Welche Funktion steht im Exponenten?"
    assert reply.text.index(llm.answer) < reply.text.index(
        "Welche Funktion steht im Exponenten?"
    )
    assert fields["message"] in reply.text
    assert json.loads(reply.context["prompt"]) == llm.calls[-1]["messages"]
    assert {"role": "user", "content": fields["message"]} in llm.calls[-1]["messages"]
    assert [item["role"] for item in reply.context["history"]] == [
        "assistant", "user", "assistant"
    ]

    action, fields = read_form(reply, "next-hint-form")
    assert fields["chat_id"] == chat_id
    fields["hint_level"] = "2"
    next_page = client.get(action, params=fields)
    assert next_page.status_code == 200
    assert next_page.context["chat_id"] == chat_id
    assert next_page.context["question_text"] == question
    assert next_page.context["hint_level"] == 2
    assert len(next_page.context["history"]) == 4
    assert json.loads(next_page.context["prompt"]) == llm.calls[-1]["messages"]
    assert question in llm.calls[-1]["messages"][-1]["content"]
    assert main_module.CHAT_STORE.get_chat(chat_id)["stack_context"] == stack


def test_randomized_variant_never_uses_local_solution_data(client, llm, start_params):
    task = main_module.TASKS[start_params["qid"]]
    start_params.update({
        "question_text": "Differenzieren Sie f(x)=7*exp(x^3-3*exp(x)).",
        "ans1": "7*exp(x^3-3*exp(x))",
        "diagnosis": "wrong_derivative_inner_exp",
        "hint_level": main_module.MAX_HINT_LEVEL
    })
    page = client.get("/start", params=start_params)
    assert page.status_code == 200
    chat_id = page.context["chat_id"]
    stack = main_module.CHAT_STORE.get_chat(chat_id)["stack_context"]
    assert stack["diagnosis_code"] == start_params["diagnosis"]
    assert stack["final_answer"] is None
    assert stack["solution_steps"] == []
    # Generic task data is safe for variants and stays attached.
    assert stack["prt_feedback"] == (
        task["diagnoses"][start_params["diagnosis"]]["title"]
    )
    assert stack["learning_goals"] == task["learning_goals"]
    assert stack["math_rules"] == task.get("math_rules", [])

    options = {name: True for name in main_module.ContextOptions.model_fields}
    response = client.post(
        f"/api/tutor/{chat_id}/message",
        json={"message": "Wie geht es weiter?", "context_options": options}
    )
    assert response.status_code == 200
    for call in llm.calls:
        prompt = json.dumps(call["messages"], ensure_ascii=False)
        assert task["model_solution"]["final_answer"] not in prompt
        assert start_params["question_text"] in prompt
        assert task["diagnoses"][start_params["diagnosis"]]["title"] in prompt
        for goal in task["learning_goals"]:
            assert goal in prompt
        # No fixed example values of the local variant leak into any prompt.
        assert "-5e^(x^2-2e^x)" not in prompt
        assert "-2e^x" not in prompt


@pytest.mark.parametrize("hint_level", [1, main_module.MAX_HINT_LEVEL])
def test_funktion_composes_template_without_local_solution(
    client, llm, start_params, hint_level
):
    task = main_module.TASKS[start_params["qid"]]
    funktion = "f(x)=7*%e^(x^3-3*%e^x)"
    start_params.update({"funktion": funktion, "hint_level": hint_level})
    page = client.get("/start", params=start_params)
    assert page.status_code == 200
    composed = task["question_text_template"].replace("{funktion}", funktion)
    assert page.context["question_text"] == composed
    chat_id = page.context["chat_id"]
    stack = main_module.CHAT_STORE.get_chat(chat_id)["stack_context"]
    assert stack["question_text"] == composed
    assert stack["learning_goals"] == task["learning_goals"]
    assert stack["prt_feedback"] == (
        task["diagnoses"][start_params["diagnosis"]]["title"]
    )
    assert stack["solution_steps"] == []
    assert stack["final_answer"] is None
    prompt = page.context["prompt"]
    assert composed in prompt
    assert task["diagnoses"][start_params["diagnosis"]]["title"] in prompt
    assert (task["model_solution"]["final_answer"] in prompt) is False
    for step in task["model_solution"]["solution_steps"]:
        assert step["description"] not in prompt


def test_funktion_and_question_text_are_mutually_exclusive(client, llm, start_params):
    start_params.update({"funktion": "f(x)=x^2", "question_text": "Volltext"})
    response = client.get("/start", params=start_params)
    assert response.status_code == 400
    assert llm.calls == []


@pytest.mark.parametrize(
    "text", ["", " \n ", "x" * (main_module.MAX_QUESTION_TEXT_LENGTH + 1)],
    ids=["empty", "whitespace", "too-long"]
)
def test_invalid_funktion_rejected_before_llm(client, llm, start_params, text):
    start_params["funktion"] = text
    response = client.get("/start", params=start_params)
    assert response.status_code == 400
    assert llm.calls == []


def test_funktion_resume_must_match_composed_context(client, llm, start_params):
    start_params["funktion"] = "f(x)=x^2"
    page = client.get("/start", params=start_params)
    chat_id = page.context["chat_id"]
    start_params.update({"chat_id": chat_id, "hint_level": 2})
    same = client.get("/start", params=start_params)
    assert same.status_code == 200
    assert same.context["chat_id"] == chat_id
    assert same.context["question_text"] == page.context["question_text"]
    start_params["funktion"] = "f(x)=x^3"
    changed = client.get("/start", params=start_params)
    assert changed.status_code == 400
    assert len(llm.calls) == 2


@pytest.mark.parametrize("hint_level", [1, 2, 3, 4])
def test_debug_prompt_preserves_local_solution_level_guards(
    client, llm, start_params, hint_level
):
    start_params["hint_level"] = hint_level
    response = client.get("/start", params=start_params)
    assert response.status_code == 200
    task = main_module.TASKS[start_params["qid"]]
    prompt = response.context["prompt"]
    assert (task["model_solution"]["final_answer"] in prompt) == (hint_level == 4)
    assert ("LÖSUNGSSCHRITTE" in prompt) == (hint_level >= 3)
    assert ('id="next-hint-form"' in response.text) == (hint_level < 4)


@pytest.mark.parametrize(
    "text", ["", " \n ", "x" * (main_module.MAX_QUESTION_TEXT_LENGTH + 1)],
    ids=["empty", "whitespace", "too-long"]
)
def test_invalid_question_text_rejected_before_llm(client, llm, start_params, text):
    start_params["question_text"] = text
    response = client.get("/start", params=start_params)
    assert response.status_code == 400
    assert llm.calls == []


def test_question_text_at_limit_is_not_truncated(client, llm, start_params):
    text = "x" * main_module.MAX_QUESTION_TEXT_LENGTH
    start_params["question_text"] = text
    response = client.get("/start", params=start_params)
    assert response.status_code == 200
    assert response.context["question_text"] == text
    assert text in response.context["prompt"]


@pytest.mark.parametrize("changes", [
    {"question_text": "Eine andere Zufallsvariante"},
    {"ans1": "Eine andere Antwort"},
    {"diagnosis": "wrong_derivative_power"},
    {"qid": "ableitung_produktregel_001"}
])
def test_resume_cannot_mix_chat_contexts(client, llm, start_params, changes):
    page = client.get("/start", params=start_params)
    chat_id = page.context["chat_id"]
    chat = main_module.CHAT_STORE.get_chat(chat_id)
    start_params.update({"chat_id": chat_id, "hint_level": 2})
    start_params.update(changes)
    response = client.get("/start", params=start_params)
    assert response.status_code == 400
    assert len(llm.calls) == 1
    assert main_module.CHAT_STORE.get_chat(chat_id) == chat


@pytest.mark.parametrize(
    "message", [None, "", " \n ", "x" * (main_module.MAX_CHAT_MESSAGE_LENGTH + 1)],
    ids=["missing", "empty", "whitespace", "too-long"]
)
def test_invalid_html_message_keeps_history_and_renders_error(
    client, llm, start_params, message
):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    if message is not None:
        fields["message"] = message
    response = client.post(action, data=fields)
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/html")
    assert 'role="alert"' in response.text
    assert response.context["history"] == page.context["history"]
    assert response.context["prompt"] is None
    assert response.context["context_options"] is None
    assert len(llm.calls) == 1


@pytest.mark.parametrize("chat_id, status", [("not-a-uuid", 400), (str(uuid4()), 404)])
def test_html_message_rejects_invalid_or_unknown_chat(client, llm, chat_id, status):
    response = client.post(f"/tutor/{chat_id}/message", data={"message": "Rückfrage"})
    assert response.status_code == status
    assert llm.calls == []


def test_html_message_rejects_model_outside_allowlist(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    fields.update({"message": "Rückfrage", "model": "not-an-allowed-model"})
    response = client.post(action, data=fields)
    assert response.status_code == 400
    assert len(llm.calls) == 1
    assert main_module.CHAT_STORE.get_messages(page.context["chat_id"]) == page.context["history"]


@pytest.mark.parametrize("error, status", [
    (LLMRateLimitError("private upstream detail"), 429),
    (LLMError("private upstream detail"), 502)
])
def test_html_llm_failure_keeps_chat_and_shows_attempted_prompt(
    client, llm, start_params, error, status
):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    fields["message"] = "Warum die Kettenregel?"
    llm.answer = error
    response = client.post(action, data=fields)
    assert response.status_code == status
    assert response.headers["content-type"].startswith("text/html")
    assert 'role="alert"' in response.text
    assert 'id="chat-form"' in response.text
    assert "private upstream detail" not in response.text
    assert response.context["hint_level"] == 1
    assert [item["role"] for item in response.context["history"]] == ["assistant", "user"]
    assert response.context["history"][-1]["content"] == fields["message"]
    assert json.loads(response.context["prompt"]) == llm.calls[-1]["messages"]


def test_failed_html_next_hint_does_not_advance_level(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "next-hint-form")
    fields["hint_level"] = "2"
    llm.answer = LLMError("private upstream detail")
    response = client.get(action, params=fields)
    assert response.status_code == 502
    assert response.context["hint_level"] == 1
    assert response.context["history"] == page.context["history"]
    assert json.loads(response.context["prompt"]) == llm.calls[-1]["messages"]
    assert "2 -" in llm.calls[-1]["messages"][0]["content"]


def test_rest_prompt_messages_and_history_follow_every_interaction(client, llm):
    default_options = main_module.model_dump_compat(
        main_module.ContextOptions()
    )
    started = client.post("/api/tutor/start", json=StartPayload.body())
    assert started.status_code == 200
    chat_id = started.json()["chat_id"]
    assert started.json()["prompt_messages"] == llm.calls[-1]["messages"]
    assert started.json()["context_options"] == default_options
    message = "Was bedeutet innere Funktion?"
    reply = client.post(f"/api/tutor/{chat_id}/message", json={"message": message})
    assert reply.status_code == 200
    assert reply.json()["hint_level"] == 1
    assert reply.json()["prompt_messages"] == llm.calls[-1]["messages"]
    assert reply.json()["context_options"] == default_options
    assert {"role": "user", "content": message} in reply.json()["prompt_messages"]

    for level in [2, 3, 4, 4]:
        response = client.post(f"/api/tutor/{chat_id}/next-hint", json={})
        assert response.status_code == 200
        assert response.json()["hint_level"] == level
        assert response.json()["prompt_messages"] == llm.calls[-1]["messages"]
        assert response.json()["context_options"] == default_options
    history = client.get(f"/api/tutor/{chat_id}/history").json()
    assert history["current_hint_level"] == 4
    assert history["messages"] == response.json()["history"]


def test_failed_rest_next_hint_does_not_advance_level(client, llm):
    started = client.post("/api/tutor/start", json=StartPayload.body())
    chat_id = started.json()["chat_id"]
    llm.answer = LLMRateLimitError("try again")
    response = client.post(f"/api/tutor/{chat_id}/next-hint", json={})
    assert response.status_code == 429
    assert main_module.CHAT_STORE.get_chat(chat_id)["current_hint_level"] == 1


def test_template_escapes_messages_and_debug_and_hides_system_history(
    client, llm, start_params
):
    unsafe = '<script>alert("test")</script> & <img src=x onerror="test()">'
    start_params.update({"question_text": unsafe, "ans1": unsafe})
    llm.answer = unsafe
    page = client.get("/start", params=start_params)
    assert page.status_code == 200
    chat_id = page.context["chat_id"]
    main_module.CHAT_STORE.add_message(chat_id, "system", "SYSTEM_ONLY_SENTINEL")
    action, fields = read_form(page, "chat-form")
    fields["message"] = unsafe
    response = client.post(action, data=fields)
    assert response.status_code == 200
    assert '<script' not in response.text
    assert '<img' not in response.text
    assert str(escape(unsafe)) in response.text
    assert "SYSTEM_ONLY_SENTINEL" not in response.text
    assert str(escape(response.context["prompt"])) in response.text
    assert unsafe not in llm.calls[-1]["messages"][0]["content"]


def test_html_retry_after_message_failure_recovers(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    fields["message"] = "Warum die Kettenregel?"
    llm.answer = LLMError("private upstream detail")
    failed = client.post(action, data=fields)

    assert failed.status_code == 502
    chat_id = failed.context["chat_id"]
    assert failed.context["retry_inline"] is True
    assert failed.context["retry_in_error"] is False
    assert failed.context["retry_hint_level"] == 1
    retry_action, retry_fields = read_form(failed, "retry-form")
    assert retry_action.endswith(f"/tutor/{chat_id}/retry")
    assert retry_fields["hint_level"] == "1"
    assert retry_fields["model"] == page.context["model"]
    assert "Erneut versuchen" in failed.text

    llm.answer = "Die innere Funktion ist der Exponent."
    recovered = client.post(retry_action, data=retry_fields)

    assert recovered.status_code == 200
    assert recovered.context["error"] is None
    assert recovered.context["chat_id"] == chat_id
    assert recovered.context["hint_level"] == 1
    assert recovered.context["retry_hint_level"] is None
    assert [item["role"] for item in recovered.context["history"]] == [
        "assistant", "user", "assistant"
    ]
    # Die Frage wurde beim Retry nicht erneut gespeichert.
    assert recovered.context["history"][-2]["content"] == fields["message"]
    assert json.loads(recovered.context["prompt"]) == llm.calls[-1]["messages"]
    assert recovered.context["context_options"] == (
        page.context["context_options"]
    )


def test_html_retry_failure_keeps_history_and_retry_button(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    fields["message"] = "Warum die Kettenregel?"
    llm.answer = LLMError("private upstream detail")
    failed = client.post(action, data=fields)
    retry_action, retry_fields = read_form(failed, "retry-form")

    again = client.post(retry_action, data=retry_fields)

    assert again.status_code == 502
    assert again.context["retry_inline"] is True
    assert [item["role"] for item in again.context["history"]] == [
        "assistant", "user"
    ]
    assert again.context["history"][-1]["content"] == fields["message"]
    assert json.loads(again.context["prompt"]) == llm.calls[-1]["messages"]
    assert "Erneut versuchen" in again.text
    assert "private upstream detail" not in again.text


def test_start_failure_retries_from_error_box(client, llm, start_params):
    llm.answer = LLMRateLimitError("private upstream detail")
    failed = client.get("/start", params=start_params)

    assert failed.status_code == 429
    chat_id = failed.context["chat_id"]
    assert failed.context["retry_inline"] is False
    assert failed.context["retry_in_error"] is True
    assert failed.context["retry_hint_level"] == 1
    retry_action, retry_fields = read_form(failed, "retry-form")
    assert retry_action.endswith(f"/tutor/{chat_id}/retry")
    assert failed.context["history"] == []

    llm.answer = "Aktiviere die Kettenregel."
    recovered = client.post(retry_action, data=retry_fields)

    assert recovered.status_code == 200
    assert recovered.context["error"] is None
    assert recovered.context["chat_id"] == chat_id
    assert recovered.context["hint_level"] == 1
    assert [item["role"] for item in recovered.context["history"]] == [
        "assistant"
    ]
    assert json.loads(recovered.context["prompt"]) == llm.calls[-1]["messages"]


def test_retry_repeats_attempted_hint_level(client, llm, start_params):
    page = client.get("/start", params=start_params)
    chat_id = page.context["chat_id"]
    resume_params = {
        **start_params,
        "chat_id": chat_id,
        "hint_level": 3
    }
    llm.answer = LLMError("private upstream detail")
    failed = client.get("/start", params=resume_params)

    assert failed.status_code == 502
    # Gespeichert bleibt die alte Stufe; der Retry wiederholt die Versuchsstufe.
    assert failed.context["hint_level"] == 1
    assert failed.context["retry_hint_level"] == 3
    retry_action, retry_fields = read_form(failed, "retry-form")
    assert retry_fields["hint_level"] == "3"

    llm.answer = "Teilschritt für Stufe 3."
    recovered = client.post(retry_action, data=retry_fields)

    assert recovered.status_code == 200
    assert recovered.context["hint_level"] == 3
    assert main_module.CHAT_STORE.get_chat(chat_id)["current_hint_level"] == 3
    assert "3 -" in llm.calls[-1]["messages"][0]["content"]


@pytest.mark.parametrize("hint_level", [0, 5, -1])
def test_retry_rejects_out_of_range_hint_level(client, llm, start_params, hint_level):
    page = client.get("/start", params=start_params)
    chat_id = page.context["chat_id"]
    response = client.post(
        f"/tutor/{chat_id}/retry",
        data={"hint_level": str(hint_level)}
    )

    assert response.status_code == 400
    assert len(llm.calls) == 1


def test_retry_rejects_lower_hint_level(client, llm, start_params):
    start_params["hint_level"] = 2
    page = client.get("/start", params=start_params)
    chat_id = page.context["chat_id"]
    assert page.context["hint_level"] == 2

    response = client.post(
        f"/tutor/{chat_id}/retry",
        data={"hint_level": "1"}
    )

    assert response.status_code == 400
    assert len(llm.calls) == 1
    assert main_module.CHAT_STORE.get_chat(chat_id)["current_hint_level"] == 2


@pytest.mark.parametrize("chat_id, status", [("not-a-uuid", 400), (str(uuid4()), 404)])
def test_retry_rejects_invalid_or_unknown_chat(client, llm, chat_id, status):
    response = client.post(f"/tutor/{chat_id}/retry", data={})
    assert response.status_code == status
    assert llm.calls == []


def test_debug_mode_hides_diagnosis_and_prompt(client, llm, start_params, monkeypatch):
    monkeypatch.setattr(main_module, "DEBUG_MODE", False)

    response = client.get("/start", params=start_params)

    assert response.status_code == 200
    assert response.context["debug_mode"] is False
    assert response.context["prompt"] is None
    assert response.context["context_options"] is None
    assert "STACK-Diagnose" not in response.text
    # Die Diagnose-ANZEIGE ist weg; das Stufen-Dropdown des Folgehints liegt
    # im Debug-Bereich und ist bei DEBUG_MODE=0 komplett ausgeblendet.
    assert f"<strong>{start_params['diagnosis']}</strong>" not in response.text
    assert 'id="debug-prompt"' not in response.text
    assert 'id="debug-context-options"' not in response.text
    assert 'id="next-hint-form"' not in response.text
    # Studierende erfahren die Hilfestufe nicht (auch nicht im Hilfetext).
    assert "Hilfestufe" not in response.text
    assert "hilfestufe" not in response.text.lower()
    # Der LLM-Kontext enthält die Diagnose weiterhin — nur die Anzeige ist weg.
    prompt_text = json.dumps(llm.calls[-1]["messages"], ensure_ascii=False)
    assert start_params["diagnosis"] in prompt_text
    # Aufgabe und Antwort bleiben sichtbar.
    assert response.context["question_text"] in response.text


def test_task_and_answer_share_one_bubble_and_debug_level_dropdown(
    client, llm, start_params
):
    response = client.get("/start", params=start_params)

    assert response.status_code == 200
    # Aufgabe und Deine Antwort liegen in derselben Bubble.
    box_start = response.text.index('<div class="box">')
    task_box = response.text[box_start:response.text.index("</div>", box_start)]
    assert "<h2>Aufgabe</h2>" in task_box
    assert "<h2>Deine Antwort</h2>" in task_box
    # Die Bubble „Weitere Hilfe“ entfällt; das Stufen-Dropdown liegt im
    # Debug-Bereich und bietet aktuelle und höhere Stufen an.
    assert "<h2>Weitere Hilfe</h2>" not in response.text
    form_start = response.text.index('id="next-hint-form"')
    form_html = response.text[form_start:response.text.index("</form>", form_start)]
    assert form_html.count("<option") == main_module.MAX_HINT_LEVEL
    assert 'value="1" selected>' in form_html
    assert "Weiterer Hinweis" not in response.text
    # Die STACK-Diagnose liegt im Debug-Details, nicht in einer eigenen Box.
    details_start = response.text.index("Debug-Informationen")
    details_html = response.text[details_start:response.text.index("</details>", details_start)]
    assert "STACK-Diagnose" in details_html
    assert start_params["diagnosis"] in details_html
    assert response.text.count("STACK-Diagnose") == 1


def test_send_button_disabled_while_question_unanswered(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "chat-form")
    fields["message"] = "Warum die Kettenregel?"
    llm.answer = LLMError("private upstream detail")
    failed = client.post(action, data=fields)

    assert failed.status_code == 502
    assert failed.context["retry_inline"] is True
    assert (
        '<button type="submit" class="hint-button" disabled>'
        in failed.text
    )
    assert "Erneut versuchen" in failed.text
    assert "noch ohne Tutor-Antwort" in failed.text

    # Retry erfolgreich -> Senden-Knopf wieder aktiv.
    retry_action, retry_fields = read_form(failed, "retry-form")
    llm.answer = "Antwort nach Retry."
    recovered = client.post(retry_action, data=retry_fields)

    assert recovered.status_code == 200
    assert (
        '<button type="submit" class="hint-button" disabled>'
        not in recovered.text
    )
    assert "noch ohne Tutor-Antwort" not in recovered.text


def test_send_button_active_when_only_hint_retry_available(client, llm, start_params):
    # Fehlgeschlagener /start: Retry liegt in der Fehlerbox, es gibt keine
    # unbeantwortete Chatfrage — der Senden-Knopf bleibt aktiv.
    llm.answer = LLMRateLimitError("private upstream detail")
    failed = client.get("/start", params=start_params)

    assert failed.status_code == 429
    assert failed.context["retry_in_error"] is True
    assert failed.context["retry_inline"] is False
    assert "Erneut versuchen" in failed.text
    assert (
        '<button type="submit" class="hint-button" disabled>'
        not in failed.text
    )
    assert "noch ohne Tutor-Antwort" not in failed.text


def test_debug_failure_page_keeps_retry_but_hides_prompt(client, llm, start_params, monkeypatch):
    monkeypatch.setattr(main_module, "DEBUG_MODE", False)
    llm.answer = LLMError("private upstream detail")
    failed = client.get("/start", params=start_params)

    assert failed.status_code == 502
    assert "Anfrage nicht abgeschlossen" in failed.text
    assert failed.context["retry_in_error"] is True
    assert "Erneut versuchen" in failed.text
    assert failed.context["prompt"] is None
    assert 'id="debug-prompt"' not in failed.text
    assert "private upstream detail" not in failed.text


def test_unknown_diagnosis_still_falls_back(client, llm, start_params):
    start_params["diagnosis"] = "unmapped_diagnosis"
    response = client.get("/start", params=start_params)
    assert response.status_code == 200
    assert response.context["diagnosis_code"] == "unknown_error"
    assert "unmapped_diagnosis" not in response.context["prompt"]


def test_old_hint_form_cannot_lower_level_or_relabel_solution_history(client, llm, start_params):
    page = client.get("/start", params=start_params)
    action, old_fields = read_form(page, "next-hint-form")
    chat_id = page.context["chat_id"]
    llm.answer = "Antwort auf Stufe 4"
    current = client.get(action, params={**old_fields, "hint_level": 4})
    assert current.status_code == 200
    # Abgesetzte/stale Formulare dürfen die Stufe nicht senken.
    response = client.get(action, params={**old_fields, "hint_level": 1})
    assert response.status_code == 400
    assert len(llm.calls) == 2
    assert main_module.CHAT_STORE.get_chat(chat_id)["current_hint_level"] == 4
    assert main_module.CHAT_STORE.get_messages(chat_id) == current.context["history"]


def test_rest_resume_cannot_lower_hint_level(client, llm):
    payload = StartPayload.body()
    payload["hint_level"] = 4
    page = client.post("/api/tutor/start", json=payload)
    assert page.status_code == 200
    payload.update({"hint_level": 1, "chat_id": page.json()["chat_id"]})
    response = client.post("/api/tutor/start", json=payload)
    assert response.status_code == 400
    assert len(llm.calls) == 1


def test_html_next_hint_accepts_browser_normalized_line_endings(client, llm, start_params):
    start_params["ans1"] = "x +\n 1"
    page = client.get("/start", params=start_params)
    action, fields = read_form(page, "next-hint-form")
    fields["hint_level"] = "2"
    fields["ans1"] = fields["ans1"].replace("\n", "\r\n")
    response = client.get(action, params=fields)
    assert response.status_code == 200
    assert response.context["chat_id"] == page.context["chat_id"]
    assert response.context["hint_level"] == 2
    assert response.context["student_answer"] == start_params["ans1"]
