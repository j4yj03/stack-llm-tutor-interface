import re
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.chat_store import ChatStore
from app.config import (
    ALLOWED_MODELS,
    MAX_HISTORY_MESSAGES,
    MAX_STUDENT_ANSWER_LENGTH,
    OLLAMA_MODEL,
    TEMPLATE_DIR
)
from app.database import initialize_database
from app.hint_policy import HintPolicy
from app.ollama_client import (
    OllamaClientError,
    call_ollama_chat
)
from app.prompt_builder import PromptBuilder
from app.schemas import (
    ChatHistoryResponse,
    ContextOptions,
    NextHintRequest,
    StackContext,
    TutorRequest,
    TutorResponse,
    UserChatRequest
)
from app.task_loader import load_all_tasks


QID_PATTERN = re.compile(
    r"^[a-zA-Z0-9_\-]+$"
)
DIAGNOSIS_PATTERN = re.compile(
    r"^[a-zA-Z0-9_\-]+$"
)

TASKS = load_all_tasks()
CHAT_STORE = ChatStore()
HINT_POLICY = HintPolicy()
PROMPT_BUILDER = PromptBuilder(HINT_POLICY)

templates = Jinja2Templates(
    directory=str(TEMPLATE_DIR)
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="STACK AI Tutor Prototype",
    version="0.2.0",
    lifespan=lifespan
)


def model_dump_compat(model) -> Dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()

    return model.dict()


def select_model(
    requested_model: Optional[str]
) -> str:
    selected_model = (
        requested_model
        or OLLAMA_MODEL
    )

    if selected_model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Nicht erlaubtes Modell",
                "allowed_models": sorted(
                    ALLOWED_MODELS
                )
            }
        )

    return selected_model


def task_to_stack_context(
    task: Dict,
    student_answer: str,
    diagnosis_code: str
) -> StackContext:
    diagnosis = task["diagnoses"][
        diagnosis_code
    ]

    solution_steps = []

    for step in task.get(
        "model_solution",
        {}
    ).get("solution_steps", []):
        text = step.get("description", "")

        if step.get("formula"):
            text += (
                " Formel: "
                + step["formula"]
            )

        if text:
            solution_steps.append(text)

    math_rules = task.get(
        "math_rules",
        []
    )

    return StackContext(
        question_id=task["question_id"],
        question_text=task["question_text"],
        student_answer=student_answer,
        diagnosis_code=diagnosis_code,
        prt_feedback=diagnosis.get("title"),
        learning_goals=task.get(
            "learning_goals",
            []
        ),
        math_rules=math_rules,
        solution_steps=solution_steps,
        final_answer=task.get(
            "model_solution",
            {}
        ).get("final_answer")
    )


def generate_hint(
    chat_id: str,
    hint_level: int,
    options: ContextOptions,
    selected_model: str
) -> str:
    chat = CHAT_STORE.get_chat(chat_id)

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat nicht gefunden"
        )

    stack_context = StackContext(
        **chat["stack_context"]
    )

    history = CHAT_STORE.get_messages(
        chat_id,
        limit=MAX_HISTORY_MESSAGES
    )

    messages = PROMPT_BUILDER.build_messages(
        stack=stack_context,
        hint_level=hint_level,
        options=options,
        history=history
    )

    try:
        return call_ollama_chat(
            messages=messages,
            model=selected_model,
            temperature=0.2,
            max_tokens=400
        )
    except OllamaClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Fehler beim Aufruf des "
                f"Hochschul-LLM: {exc}"
            )
        ) from exc


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tasks_loaded": len(TASKS),
        "default_model": OLLAMA_MODEL
    }


@app.get("/tasks")
def list_tasks():
    return [
        {
            "question_id": task["question_id"],
            "topic": task["topic"],
            "subtopic": task["subtopic"],
            "status": task["status"]
        }
        for task in TASKS.values()
    ]


@app.get(
    "/start",
    response_class=HTMLResponse
)
def start(
    request: Request,
    qid: str = Query(...),
    diagnosis: str = Query("unknown_error"),
    ans1: str = Query(""),
    hint_level: int = Query(
        1,
        ge=1,
        le=4
    ),
    model: Optional[str] = Query(None),
    chat_id: Optional[str] = Query(None)
):
    if not QID_PATTERN.fullmatch(qid):
        raise HTTPException(
            status_code=400,
            detail="Ungültige question_id"
        )

    if not DIAGNOSIS_PATTERN.fullmatch(
        diagnosis
    ):
        raise HTTPException(
            status_code=400,
            detail="Ungültiger diagnosis-Code"
        )

    if qid not in TASKS:
        raise HTTPException(
            status_code=404,
            detail="Unbekannte question_id"
        )

    if not ans1.strip():
        raise HTTPException(
            status_code=400,
            detail="Studierendenantwort fehlt"
        )

    if len(ans1) > MAX_STUDENT_ANSWER_LENGTH:
        raise HTTPException(
            status_code=400,
            detail="Studierendenantwort ist zu lang"
        )

    selected_model = select_model(model)
    task = TASKS[qid]

    if diagnosis not in task["diagnoses"]:
        diagnosis = "unknown_error"

    if diagnosis not in task["diagnoses"]:
        raise HTTPException(
            status_code=500,
            detail=(
                "unknown_error ist in der "
                "Aufgaben-JSON nicht definiert"
            )
        )

    stack_context = task_to_stack_context(
        task=task,
        student_answer=ans1,
        diagnosis_code=diagnosis
    )

    if chat_id:
        try:
            chat = CHAT_STORE.get_chat(chat_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc)
            ) from exc

        if chat is None:
            raise HTTPException(
                status_code=404,
                detail="Chat nicht gefunden"
            )

        if chat["question_id"] != qid:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Chat gehört zu einer "
                    "anderen Aufgabe"
                )
            )

        CHAT_STORE.set_hint_level(
            chat_id,
            hint_level
        )
    else:
        chat_id = CHAT_STORE.create_chat(
            question_id=qid,
            stack_context=model_dump_compat(
                stack_context
            ),
            hint_level=hint_level
        )

    context_options = ContextOptions(
        include_question_text=True,
        include_student_answer=True,
        include_diagnosis_code=True,
        include_prt_feedback=True,
        include_score=False,
        include_learning_goals=False,
        include_math_rules=False,
        include_solution_steps=True,
        include_final_answer=True,
        include_chat_history=True
    )

    tutor_answer = generate_hint(
        chat_id=chat_id,
        hint_level=hint_level,
        options=context_options,
        selected_model=selected_model
    )

    CHAT_STORE.add_message(
        chat_id,
        "assistant",
        tutor_answer
    )

    chat = CHAT_STORE.get_chat(chat_id)
    history = CHAT_STORE.get_messages(
        chat_id
    )

    return templates.TemplateResponse(
        "tutor_page.html",
        {
            "request": request,
            "chat_id": chat_id,
            "question_id": qid,
            "topic": task["topic"],
            "subtopic": task["subtopic"],
            "question_text": task[
                "question_text"
            ],
            "student_answer": ans1,
            "diagnosis_code": diagnosis,
            "diagnosis_title": task[
                "diagnoses"
            ][diagnosis]["title"],
            "hint_level": hint_level,
            "model": selected_model,
            "tutor_answer": tutor_answer,
            "history": history,
            "max_hint_level": 4
        }
    )


@app.post(
    "/api/tutor/start",
    response_model=TutorResponse
)
def start_tutor(
    request: TutorRequest
):
    selected_model = select_model(
        request.model
    )

    if request.chat_id:
        try:
            chat = CHAT_STORE.get_chat(
                request.chat_id
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc)
            ) from exc

        if chat is None:
            raise HTTPException(
                status_code=404,
                detail="Chat nicht gefunden"
            )

        chat_id = request.chat_id
    else:
        chat_id = CHAT_STORE.create_chat(
            question_id=(
                request.stack.question_id
            ),
            stack_context=model_dump_compat(
                request.stack
            ),
            hint_level=request.hint_level
        )

    if request.user_message:
        CHAT_STORE.add_message(
            chat_id,
            "user",
            request.user_message
        )

    tutor_answer = generate_hint(
        chat_id=chat_id,
        hint_level=request.hint_level,
        options=request.context_options,
        selected_model=selected_model
    )

    CHAT_STORE.set_hint_level(
        chat_id,
        request.hint_level
    )

    CHAT_STORE.add_message(
        chat_id,
        "assistant",
        tutor_answer
    )

    return {
        "chat_id": chat_id,
        "question_id": (
            request.stack.question_id
        ),
        "hint_level": request.hint_level,
        "model": selected_model,
        "hint": tutor_answer,
        "history": CHAT_STORE.get_messages(
            chat_id
        )
    }


@app.post(
    "/api/tutor/{chat_id}/next-hint",
    response_model=TutorResponse
)
def next_hint(
    chat_id: str,
    request: NextHintRequest
):
    try:
        chat = CHAT_STORE.get_chat(chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat nicht gefunden"
        )

    selected_model = select_model(
        request.model
    )

    hint_level = CHAT_STORE.next_hint_level(
        chat_id
    )

    tutor_answer = generate_hint(
        chat_id=chat_id,
        hint_level=hint_level,
        options=request.context_options,
        selected_model=selected_model
    )

    CHAT_STORE.add_message(
        chat_id,
        "assistant",
        tutor_answer
    )

    return {
        "chat_id": chat_id,
        "question_id": chat["question_id"],
        "hint_level": hint_level,
        "model": selected_model,
        "hint": tutor_answer,
        "history": CHAT_STORE.get_messages(
            chat_id
        )
    }


@app.post(
    "/api/tutor/{chat_id}/message",
    response_model=TutorResponse
)
def chat_message(
    chat_id: str,
    request: UserChatRequest
):
    try:
        chat = CHAT_STORE.get_chat(chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat nicht gefunden"
        )

    selected_model = select_model(
        request.model
    )

    CHAT_STORE.add_message(
        chat_id,
        "user",
        request.message
    )

    hint_level = chat[
        "current_hint_level"
    ]

    tutor_answer = generate_hint(
        chat_id=chat_id,
        hint_level=hint_level,
        options=request.context_options,
        selected_model=selected_model
    )

    CHAT_STORE.add_message(
        chat_id,
        "assistant",
        tutor_answer
    )

    return {
        "chat_id": chat_id,
        "question_id": chat["question_id"],
        "hint_level": hint_level,
        "model": selected_model,
        "hint": tutor_answer,
        "history": CHAT_STORE.get_messages(
            chat_id
        )
    }


@app.get(
    "/api/tutor/{chat_id}/history",
    response_model=ChatHistoryResponse
)
def get_history(chat_id: str):
    try:
        chat = CHAT_STORE.get_chat(chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat nicht gefunden"
        )

    return {
        "chat_id": chat_id,
        "question_id": chat["question_id"],
        "current_hint_level": chat[
            "current_hint_level"
        ],
        "messages": CHAT_STORE.get_messages(
            chat_id
        )
    }