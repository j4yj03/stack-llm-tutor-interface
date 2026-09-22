import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple

from fastapi import (
    FastAPI,
    Form,
    HTTPException,
    Query,
    Request
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.chat_store import ChatStore
from app.config import (
    ALLOWED_MODELS,
    DEBUG_MODE,
    LLM_MODEL,
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_HINT_LEVEL,
    MAX_HISTORY_MESSAGES,
    MAX_QUESTION_TEXT_LENGTH,
    MAX_STUDENT_ANSWER_LENGTH,
    TEMPLATE_DIR
)
from app.database import initialize_database
from app.hint_policy import HintPolicy
from app.llm import (
    LLMError,
    LLMRateLimitError,
    create_llm_client
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

logger = logging.getLogger(__name__)

TASKS = load_all_tasks()
CHAT_STORE = ChatStore()
HINT_POLICY = HintPolicy()
PROMPT_BUILDER = PromptBuilder(HINT_POLICY)

# Kontextoptionen der HTML-Flows (/start, Chatnachricht, Retry): die
# Defaultwerte der ContextOptions kommen aus CONTEXT_OPTIONS in der .env.
HTML_CONTEXT_OPTIONS = ContextOptions()

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
        or LLM_MODEL
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
    diagnosis_code: str,
    question_text: Optional[str] = None
) -> StackContext:
    if question_text is not None and question_text != task["question_text"]:
        # Moodle variant: the question text comes from STACK, so only generic
        # task data (goals, rules, diagnosis title) may be attached. The local
        # model solution holds example values of a fixed variant.
        diagnosis = task["diagnoses"][diagnosis_code]

        return StackContext(
            question_id=task["question_id"],
            question_text=question_text,
            student_answer=student_answer,
            diagnosis_code=diagnosis_code,
            prt_feedback=diagnosis.get("title"),
            learning_goals=task.get(
                "learning_goals",
                []
            ),
            math_rules=task.get(
                "math_rules",
                []
            )
        )

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


def get_chat_or_404(chat_id: str) -> Dict:
    try:
        chat = CHAT_STORE.get_chat(chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if chat is None:
        raise HTTPException(status_code=404, detail="Chat nicht gefunden")

    return chat


class HintGenerationError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        prompt_messages: List[Dict[str, str]]
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.prompt_messages = prompt_messages


def generate_hint(
    chat_id: str,
    hint_level: int,
    options: ContextOptions,
    selected_model: str
) -> Tuple[str, List[Dict[str, str]]]:
    chat = get_chat_or_404(chat_id)

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
        tutor_answer = create_llm_client().chat(
            messages=messages,
            model=selected_model,
            temperature=0.2,
            max_tokens=400
        )
    except LLMRateLimitError as exc:
        # Serverseitige Diagnose; enthält keine Keys oder Auth-Header.
        logger.warning(
            "LLM-Ratelimit bei Modell %s: %s",
            selected_model,
            exc
        )
        raise HintGenerationError(
            status_code=429,
            detail=(
                "Rate-Limit des LLM-Dienstes erreicht. "
                "Bitte kurze Zeit warten."
            ),
            prompt_messages=messages
        ) from exc
    except LLMError as exc:
        logger.warning(
            "LLM-Fehler bei Modell %s: %s",
            selected_model,
            exc
        )
        raise HintGenerationError(
            status_code=502,
            detail=(
                "Fehler beim Aufruf des Hochschul-LLM. "
                "Bitte später erneut versuchen."
            ),
            prompt_messages=messages
        ) from exc

    return tutor_answer, messages


def render_tutor_page(
    request: Request,
    chat_id: str,
    selected_model: str,
    prompt_messages: Optional[List[Dict[str, str]]] = None,
    context_options: Optional[ContextOptions] = None,
    error: Optional[str] = None,
    status_code: int = 200,
    message_draft: str = "",
    retry_hint_level: Optional[int] = None
) -> HTMLResponse:
    chat = get_chat_or_404(chat_id)
    stack = StackContext(**chat["stack_context"])
    history = CHAT_STORE.get_messages(chat_id)

    # Genau ein Retry-Steuerlement pro Fehlerseite: inline neben der
    # unbeantworteten Frage im Chat, sonst in der Fehlerbox (z. B. nach
    # fehlgeschlagenem /start-Aufruf ohne Chatnachricht).
    retry_available = (
        error is not None
        and retry_hint_level is not None
    )
    visible = [
        message
        for message in history
        if message["role"] in ("user", "assistant")
    ]
    retry_inline = (
        retry_available
        and bool(visible)
        and visible[-1]["role"] == "user"
    )

    # Neueste Beiträge zuerst: Das Chat-Panel ist ein CSS-Scroll-Container
    # (flex column-reverse) und initial am neuesten Beitrag verankert —
    # ganz ohne JavaScript.
    chat_messages = list(reversed(visible))

    # Debug-Informationen (Prompt, ContextOptions) verlassen den Server im
    # DEBUG_MODE nicht — der Debug-Bereich des Templates blendet sie aus.
    prompt_json = None
    if DEBUG_MODE and prompt_messages is not None:
        prompt_json = json.dumps(
            prompt_messages,
            indent=2,
            ensure_ascii=False
        )

    options_json = None
    if DEBUG_MODE and context_options is not None:
        options_json = json.dumps(
            model_dump_compat(context_options),
            indent=2,
            ensure_ascii=False
        )

    return templates.TemplateResponse(
        request=request,
        name="tutor_page.html",
        context={
            "chat_id": chat_id,
            "question_id": stack.question_id,
            "question_text": stack.question_text,
            "student_answer": stack.student_answer,
            "diagnosis_code": stack.diagnosis_code or "unknown_error",
            "diagnosis_title": stack.prt_feedback,
            "hint_level": chat["current_hint_level"],
            "model": selected_model,
            "history": history,
            "chat_messages": chat_messages,
            "prompt": prompt_json,
            "context_options": options_json,
            "max_hint_level": MAX_HINT_LEVEL,
            "max_chat_message_length": MAX_CHAT_MESSAGE_LENGTH,
            "error": error,
            "message_draft": message_draft,
            "debug_mode": DEBUG_MODE,
            "retry_hint_level": retry_hint_level,
            "retry_inline": retry_inline,
            "retry_in_error": (
                retry_available and not retry_inline
            )
        },
        status_code=status_code
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tasks_loaded": len(TASKS),
        "default_model": LLM_MODEL
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
        le=MAX_HINT_LEVEL
    ),
    model: Optional[str] = Query(None),
    chat_id: Optional[str] = Query(None),
    question_text: Optional[str] = Query(None),
    funktion: Optional[str] = Query(None)
) -> HTMLResponse:
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

    if question_text is not None and funktion is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bitte nur question_text oder funktion "
                "übergeben, nicht beides."
            )
        )

    if question_text is not None:
        if len(question_text) > MAX_QUESTION_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="Aufgabenstellung ist zu lang"
            )
        question_text = question_text.strip()
        if not question_text:
            raise HTTPException(
                status_code=400,
                detail="Aufgabenstellung darf nicht leer sein"
            )

    if funktion is not None:
        if len(funktion) > MAX_QUESTION_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="Funktionsbeschreibung ist zu lang"
            )
        funktion = funktion.strip()
        if not funktion:
            raise HTTPException(
                status_code=400,
                detail="Funktionsbeschreibung darf nicht leer sein"
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

    if funktion is not None:
        # Generic text template from the task JSON + instantiated function
        # from Moodle/STACK. The composed text drives display, prompt and
        # the stored chat context; only generic local data is attached.
        template = task.get("question_text_template")

        if not template:
            raise HTTPException(
                status_code=500,
                detail=(
                    "question_text_template fehlt in der Aufgaben-JSON"
                )
            )

        question_text = template.replace(
            "{funktion}",
            funktion
        )

    if chat_id:
        chat = get_chat_or_404(chat_id)

        if chat["question_id"] != qid:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Chat gehört zu einer "
                    "anderen Aufgabe"
                )
            )

        stack_context = StackContext(**chat["stack_context"])
        if (
            # HTML forms normalize line endings to CRLF on submission.
            ans1.replace("\r\n", "\n").replace("\r", "\n")
            != stack_context.student_answer.replace("\r\n", "\n").replace("\r", "\n")
            or diagnosis != stack_context.diagnosis_code
            or (question_text is not None
                and question_text != stack_context.question_text)
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Aufgabe, Antwort oder Diagnose passen nicht zum Chat. "
                    "Bitte einen neuen Tutorlink ohne chat_id öffnen."
                )
            )
        if hint_level < chat["current_hint_level"]:
            raise HTTPException(
                status_code=400,
                detail="Die Hilfestufe eines bestehenden Chats darf nicht sinken."
            )
    else:
        stack_context = task_to_stack_context(
            task=task,
            student_answer=ans1,
            diagnosis_code=diagnosis,
            question_text=question_text
        )
        chat_id = CHAT_STORE.create_chat(
            question_id=qid,
            stack_context=model_dump_compat(
                stack_context
            ),
            hint_level=hint_level
        )

    context_options = HTML_CONTEXT_OPTIONS

    try:
        tutor_answer, messages = generate_hint(
            chat_id=chat_id,
            hint_level=hint_level,
            options=context_options,
            selected_model=selected_model
        )
    except HintGenerationError as exc:
        return render_tutor_page(
            request, chat_id, selected_model,
            prompt_messages=exc.prompt_messages,
            context_options=context_options,
            error=exc.detail,
            status_code=exc.status_code,
            retry_hint_level=hint_level
        )

    CHAT_STORE.set_hint_level(chat_id, hint_level)
    CHAT_STORE.add_message(
        chat_id,
        "assistant",
        tutor_answer
    )

    return render_tutor_page(
        request, chat_id, selected_model, prompt_messages=messages,
        context_options=context_options
    )


@app.post("/tutor/{chat_id}/message", response_class=HTMLResponse)
def tutor_message_page(
    request: Request,
    chat_id: str,
    message: str = Form(""),
    model: Optional[str] = Form(None)
) -> HTMLResponse:
    chat = get_chat_or_404(chat_id)
    selected_model = select_model(model)

    if not message.strip() or len(message) > MAX_CHAT_MESSAGE_LENGTH:
        return render_tutor_page(
            request, chat_id, selected_model,
            error=(
                "Bitte eine Nachricht mit 1 bis "
                f"{MAX_CHAT_MESSAGE_LENGTH} Zeichen eingeben."
            ),
            status_code=400,
            message_draft=message[:MAX_CHAT_MESSAGE_LENGTH]
        )

    CHAT_STORE.add_message(chat_id, "user", message.strip())
    context_options = HTML_CONTEXT_OPTIONS
    try:
        tutor_answer, messages = generate_hint(
            chat_id=chat_id,
            hint_level=chat["current_hint_level"],
            options=context_options,
            selected_model=selected_model
        )
    except HintGenerationError as exc:
        return render_tutor_page(
            request, chat_id, selected_model,
            prompt_messages=exc.prompt_messages,
            context_options=context_options,
            error=f"{exc.detail} Deine Nachricht wurde im Verlauf gespeichert.",
            status_code=exc.status_code,
            retry_hint_level=chat["current_hint_level"]
        )

    CHAT_STORE.add_message(chat_id, "assistant", tutor_answer)
    return render_tutor_page(
        request, chat_id, selected_model, prompt_messages=messages,
        context_options=context_options
    )


@app.post("/tutor/{chat_id}/retry", response_class=HTMLResponse)
def tutor_retry_page(
    request: Request,
    chat_id: str,
    model: Optional[str] = Form(None),
    hint_level: Optional[int] = Form(None)
) -> HTMLResponse:
    """Wiederholt nur die fehlgeschlagene Generierung: die gespeicherte
    Nutzerfrage wird nicht erneut eingetragen, bei Erfolg wandert nur
    die neue Assistant-Antwort in den Verlauf."""
    chat = get_chat_or_404(chat_id)
    selected_model = select_model(model)

    if hint_level is None:
        target_level = chat["current_hint_level"]
    else:
        target_level = hint_level

        if not 1 <= target_level <= MAX_HINT_LEVEL:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Hilfestufe muss zwischen 1 und "
                    f"{MAX_HINT_LEVEL} liegen."
                )
            )

        if target_level < chat["current_hint_level"]:
            raise HTTPException(
                status_code=400,
                detail="Die Hilfestufe eines bestehenden Chats darf nicht sinken."
            )

    try:
        tutor_answer, messages = generate_hint(
            chat_id=chat_id,
            hint_level=target_level,
            options=HTML_CONTEXT_OPTIONS,
            selected_model=selected_model
        )
    except HintGenerationError as exc:
        return render_tutor_page(
            request, chat_id, selected_model,
            prompt_messages=exc.prompt_messages,
            context_options=HTML_CONTEXT_OPTIONS,
            error=exc.detail,
            status_code=exc.status_code,
            retry_hint_level=target_level
        )

    CHAT_STORE.set_hint_level(chat_id, target_level)
    CHAT_STORE.add_message(chat_id, "assistant", tutor_answer)
    return render_tutor_page(
        request, chat_id, selected_model, prompt_messages=messages,
        context_options=HTML_CONTEXT_OPTIONS
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

        if request.hint_level < chat["current_hint_level"]:
            raise HTTPException(
                status_code=400,
                detail="Die Hilfestufe eines bestehenden Chats darf nicht sinken."
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

    tutor_answer, messages = generate_hint(
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
        "prompt_messages": messages,
        "context_options": model_dump_compat(
            request.context_options
        ),
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

    hint_level = min(
        chat["current_hint_level"] + 1,
        MAX_HINT_LEVEL
    )

    tutor_answer, messages = generate_hint(
        chat_id=chat_id,
        hint_level=hint_level,
        options=request.context_options,
        selected_model=selected_model
    )

    CHAT_STORE.set_hint_level(chat_id, hint_level)
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
        "prompt_messages": messages,
        "context_options": model_dump_compat(
            request.context_options
        ),
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

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein")

    CHAT_STORE.add_message(
        chat_id,
        "user",
        request.message
    )

    hint_level = chat[
        "current_hint_level"
    ]

    tutor_answer, messages = generate_hint(
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
        "prompt_messages": messages,
        "context_options": model_dump_compat(
            request.context_options
        ),
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
