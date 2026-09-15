import os
from pathlib import Path
from typing import Set


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

MAX_STUDENT_ANSWER_LENGTH = int(
    os.getenv("MAX_STUDENT_ANSWER_LENGTH", "2000")
)

MAX_HISTORY_MESSAGES = int(
    os.getenv("MAX_HISTORY_MESSAGES", "12")
)

MAX_HINT_LEVEL = 4
