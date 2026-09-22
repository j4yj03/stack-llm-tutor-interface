import os
from pathlib import Path
from typing import Dict, Set


BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

TASK_DIR = BASE_DIR / "tasks"
SCHEMA_PATH = (
    BASE_DIR
    / "schemas"
    / "stack_ai_tutor_task.schema.json"
)
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
HINT_LEVELS_PATH = (
    BASE_DIR
    / "config"
    / "hint_levels.json"
)

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        str(BASE_DIR / "data" / "tutor.db")
    )
)

# Neutrale LLM-Konfiguration (siehe AGENTS.md):
#   LLM_API_MODE: saia | ollama
#   LLM_BASE_URL: Basis-URL inkl. ggf. /v1
#   LLM_API_KEY:  nur lokal in code/.env setzen
LLM_API_MODE = os.getenv(
    "LLM_API_MODE",
    "saia"
).strip().lower()

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://chat-ai.academiccloud.de/v1"
).rstrip("/")

LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    ""
).strip()

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen3.8-27b"
)

LLM_TIMEOUT = int(
    os.getenv("LLM_TIMEOUT", "180")
)

# Wartezeit vor dem einen automatischen Wiederholungsversuch,
# wenn das Gateway einen Chat-Aufruf mit HTTP 5xx abweist.
LLM_RETRY_DELAY = float(
    os.getenv("LLM_RETRY_DELAY", "2")
)

# Reasoning/Thinking der Modelle unterdrücken
# (didaktische Hints, keine Token-Verschwendung).
# 1/true = aus (Standard), 0/false = zulassen.
LLM_DISABLE_THINKING = os.getenv(
    "LLM_DISABLE_THINKING",
    "1"
).strip().lower() in ("1", "true", "yes")

# Verifiziert am 15.09.2026 via GET /v1/models
DEFAULT_ALLOWED_MODELS: Set[str] = {
    "qwen3.8-27b",
    "qwen3.6-35b-a3b",
    "qwen3.5-122b-a10b",
    "gemma-4-31b-it",
    "openai-gpt-oss-120b",
    "mistral-medium-3.5-128b",
    "glm-4.7",
    "meta-llama-3.1-8b-instruct"
}

ALLOWED_MODELS: Set[str] = {
    model.strip()
    for model in os.getenv(
        "LLM_ALLOWED_MODELS",
        ""
    ).split(",")
    if model.strip()
}

if not ALLOWED_MODELS:
    ALLOWED_MODELS = set(
        DEFAULT_ALLOWED_MODELS
    )

# Das Default-Modell bleibt immer auswählbar.
ALLOWED_MODELS.add(LLM_MODEL)


# Aktive Kontextoptionen der Tutor-Flows (Kommagetrennt in CONTEXT_OPTIONS).
# Gültig sind die ContextOptions-Felder, mit oder ohne Präfix "include_".
# Unbekannte Namen verhindern bewusst den Serverstart (Fail-fast).
_VALID_CONTEXT_OPTIONS = frozenset({
    "question_text",
    "student_answer",
    "diagnosis_code",
    "prt_feedback",
    "score",
    "learning_goals",
    "math_rules",
    "solution_steps",
    "final_answer",
    "chat_history",
})

_DEFAULT_CONTEXT_OPTIONS = (
    "question_text,student_answer,diagnosis_code,prt_feedback,"
    "learning_goals,solution_steps,final_answer,chat_history"
)


def _parse_context_options(raw: str) -> Dict[str, bool]:
    enabled: Dict[str, bool] = {
        name: False
        for name in _VALID_CONTEXT_OPTIONS
    }

    for name in raw.split(","):
        name = name.strip().lower().replace("-", "_")

        if not name:
            continue

        if name.startswith("include_"):
            name = name[len("include_"):]

        if name not in _VALID_CONTEXT_OPTIONS:
            raise RuntimeError(
                f"Unbekannte Kontextoption in CONTEXT_OPTIONS: "
                f"'{name}'. Gültige Werte: "
                f"{sorted(_VALID_CONTEXT_OPTIONS)}"
            )

        enabled[name] = True

    return enabled


CONTEXT_OPTIONS_ENABLED: Dict[str, bool] = _parse_context_options(
    os.getenv("CONTEXT_OPTIONS", _DEFAULT_CONTEXT_OPTIONS)
)


# Debug-Ansicht der Tutor-Seite: 1 = Debug-Details (Hilfestufen-Dropdown,
# STACK-Diagnose, Prompt-/Options-Debugger) sichtbar (Entwicklung),
# 0 = für Studierende ausgeblendet.
DEBUG_MODE = os.getenv(
    "DEBUG_MODE",
    "1"
).strip().lower() in ("1", "true", "yes")

MAX_STUDENT_ANSWER_LENGTH = int(
    os.getenv("MAX_STUDENT_ANSWER_LENGTH", "2000")
)

MAX_QUESTION_TEXT_LENGTH = int(
    os.getenv("MAX_QUESTION_TEXT_LENGTH", "5000")
)

# Obergrenze des gespeicherten Aufgabentexts (JSON-API und Chat-Persistenz);
# kompatibel zum bisher festen Limit von 10000 Zeichen. Der aus Textbaustein
# und übertragener Funktion zusammengesetzte Text bleibt darunter.
MAX_CONTEXT_QUESTION_TEXT = max(
    10000,
    MAX_QUESTION_TEXT_LENGTH
)

MAX_CHAT_MESSAGE_LENGTH = int(
    os.getenv("MAX_CHAT_MESSAGE_LENGTH", "2000")
)

MAX_HISTORY_MESSAGES = int(
    os.getenv("MAX_HISTORY_MESSAGES", "12")
)

MAX_HINT_LEVEL = 4
