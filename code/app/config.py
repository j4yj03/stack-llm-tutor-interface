import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Set


BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} muss ein boolescher Wert sein (1/0, true/false)")


def _env_int(
    name: str,
    default: int,
    minimum: int,
    maximum: Optional[int] = None
) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} muss eine Ganzzahl sein") from exc
    if value < minimum or (maximum is not None and value > maximum):
        raise RuntimeError(
            f"{name} muss mindestens {minimum}"
            + (f" und hoechstens {maximum}" if maximum is not None else "")
            + " sein"
        )
    return value


def _env_float(
    name: str,
    default: float,
    minimum: float,
    maximum: Optional[float] = None
) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} muss eine endliche Zahl sein") from exc
    if (
        not math.isfinite(value)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise RuntimeError(
            f"{name} muss endlich und mindestens {minimum}"
            + (f" und hoechstens {maximum}" if maximum is not None else "")
            + " sein"
        )
    return value


def _env_choice(name: str, default: str, choices: Set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in choices:
        raise RuntimeError(f"{name}: erlaubte Werte sind {sorted(choices)}")
    return value


TASK_DIR = BASE_DIR / "tasks"
SCHEMA_PATH = (
    BASE_DIR
    / "schemas"
    / "stack_ai_tutor_task.schema.json"
)
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
_hint_levels_path = os.getenv("HINT_LEVELS_PATH", "config/hint_levels.json").strip()
if not _hint_levels_path:
    raise RuntimeError("HINT_LEVELS_PATH darf nicht leer sein")
HINT_LEVELS_PATH = Path(_hint_levels_path)
if not HINT_LEVELS_PATH.is_absolute():
    HINT_LEVELS_PATH = BASE_DIR / HINT_LEVELS_PATH

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

LLM_TIMEOUT = _env_int("LLM_TIMEOUT", 180, 1)
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.2, 0.0, 2.0)
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 400, 1, 32768)

# Wartezeit vor dem einen automatischen Wiederholungsversuch,
# wenn das Gateway einen Chat-Aufruf mit HTTP 5xx abweist.
LLM_RETRY_DELAY = _env_float("LLM_RETRY_DELAY", 2.0, 0.0)

# Reasoning/Thinking der Modelle unterdrücken
# (didaktische Hints, keine Token-Verschwendung).
# 1/true = aus (Standard), 0/false = zulassen.
LLM_DISABLE_THINKING = _env_bool("LLM_DISABLE_THINKING", True)

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


def _parse_context_options(
    raw: str,
    variable: str = "CONTEXT_OPTIONS"
) -> Dict[str, bool]:
    enabled: Dict[str, bool] = {
        name: False
        for name in _VALID_CONTEXT_OPTIONS
    }

    for name in raw.replace(";", ",").split(","):
        name = name.strip().lower().replace("-", "_")

        if not name:
            continue

        if name.startswith("include_"):
            name = name[len("include_"):]

        if name not in _VALID_CONTEXT_OPTIONS:
            raise RuntimeError(
                f"Unbekannte Kontextoption in {variable}: "
                f"'{name}'. Gueltige Werte: "
                f"{sorted(_VALID_CONTEXT_OPTIONS)}"
            )

        enabled[name] = True

    return enabled


CONTEXT_OPTIONS_ENABLED: Dict[str, bool] = _parse_context_options(
    os.getenv("CONTEXT_OPTIONS", _DEFAULT_CONTEXT_OPTIONS)
)

TUTOR_STAGE0_CONTEXT_OPTIONS: Dict[str, bool] = _parse_context_options(
    os.getenv(
        "TUTOR_STAGE0_CONTEXT_OPTIONS",
        "question_text,student_answer,learning_goals,math_rules,chat_history"
    ),
    "TUTOR_STAGE0_CONTEXT_OPTIONS"
)


# Debug-Ansicht der Tutor-Seite: 1 = Debug-Details (Hilfestufen-Dropdown,
# STACK-Diagnose, Prompt-/Options-Debugger) sichtbar (Entwicklung),
# 0 = für Studierende ausgeblendet.
DEBUG_MODE = _env_bool("DEBUG_MODE", True)

MAX_STUDENT_ANSWER_LENGTH = _env_int("MAX_STUDENT_ANSWER_LENGTH", 2000, 1)
MAX_QUESTION_TEXT_LENGTH = _env_int("MAX_QUESTION_TEXT_LENGTH", 5000, 1)

# Obergrenze des gespeicherten Aufgabentexts (JSON-API und Chat-Persistenz);
# kompatibel zum bisher festen Limit von 10000 Zeichen. Der aus Textbaustein
# und übertragener Funktion zusammengesetzte Text bleibt darunter.
MAX_CONTEXT_QUESTION_TEXT = max(
    10000,
    MAX_QUESTION_TEXT_LENGTH
)

MAX_CHAT_MESSAGE_LENGTH = _env_int("MAX_CHAT_MESSAGE_LENGTH", 2000, 1)
MAX_HISTORY_MESSAGES = _env_int("MAX_HISTORY_MESSAGES", 12, 1)

MIN_HINT_LEVEL = 0
MAX_HINT_LEVEL = _env_int("MAX_HINT_LEVEL", 4, MIN_HINT_LEVEL, 32)
DEFAULT_HINT_LEVEL = _env_int(
    "TUTOR_START_LEVEL", 1, MIN_HINT_LEVEL, MAX_HINT_LEVEL
)
TUTOR_START_MODE = _env_choice("TUTOR_START_MODE", "fixed", {"fixed", "individual"})
TUTOR_DIAGNOSIS_MODE = _env_choice(
    "TUTOR_DIAGNOSIS_MODE", "provided", {"provided", "model", "none"}
)
TUTOR_POLICY_MODE = _env_choice("TUTOR_POLICY_MODE", "tutor", {"tutor", "general"})
TUTOR_RESPONSE_FORMAT = _env_choice(
    "TUTOR_RESPONSE_FORMAT", "text", {"text", "structured"}
)
TUTOR_RULES_ID = os.getenv("TUTOR_RULES_ID", "default-policy").strip()
if not TUTOR_RULES_ID:
    raise RuntimeError("TUTOR_RULES_ID darf nicht leer sein")

TUTOR_ASK_ACTIVATING_QUESTION = _env_bool("TUTOR_ASK_ACTIVATING_QUESTION", True)
TUTOR_HIDE_HINT_LEVEL = _env_bool("TUTOR_HIDE_HINT_LEVEL", True)
TUTOR_ENFORCE_WORD_LIMIT = _env_bool("TUTOR_ENFORCE_WORD_LIMIT", True)

# LaTeX-Notationsregel im Tutormodus: 1 fordert LaTeX-Ausgabe mit \( \)/$$ $$
# (Anzeige der Formeln auf der Tutorseite via KaTeX); 0 entfernt diese Regel.
TUTOR_LATEX_NOTATION = _env_bool("TUTOR_LATEX_NOTATION", True)

TUTOR_ADAPTIVE_ENABLED = _env_bool("TUTOR_ADAPTIVE_ENABLED", False)
TUTOR_ADAPTIVE_AFTER_SECONDS = _env_float("TUTOR_ADAPTIVE_AFTER_SECONDS", 120.0, 0.0)
TUTOR_ADAPTIVE_STEP = _env_int("TUTOR_ADAPTIVE_STEP", 1, 1)
TUTOR_ADAPTIVE_MAX_LEVEL = _env_int(
    "TUTOR_ADAPTIVE_MAX_LEVEL", MAX_HINT_LEVEL, MIN_HINT_LEVEL, MAX_HINT_LEVEL
)
TUTOR_ADAPTIVE_CONFUSION_PHRASES: List[str] = list(dict.fromkeys(
    phrase.strip().lower()
    for phrase in os.getenv(
        "TUTOR_ADAPTIVE_CONFUSION_PHRASES",
        "ich verstehe nicht,keine ahnung,ich weiss nicht,no idea"
    ).replace(";", ",").split(",")
    if phrase.strip()
))

EVALUATION_API_ENABLED = _env_bool("EVALUATION_API_ENABLED", False)
EVALUATION_API_TOKEN = os.getenv("EVALUATION_API_TOKEN", "").strip()
if EVALUATION_API_ENABLED and not EVALUATION_API_TOKEN:
    raise RuntimeError("EVALUATION_API_TOKEN ist bei EVALUATION_API_ENABLED=1 erforderlich")
EVALUATION_JUDGE_MODEL = os.getenv("EVALUATION_JUDGE_MODEL", "").strip()
EVALUATION_JUDGE_TEMPERATURE = _env_float("EVALUATION_JUDGE_TEMPERATURE", 0.0, 0.0, 2.0)
EVALUATION_JUDGE_MAX_TOKENS = _env_int("EVALUATION_JUDGE_MAX_TOKENS", 1200, 1, 32768)
