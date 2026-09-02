import os
from pathlib import Path
from typing import Set


BASE_DIR = Path(__file__).resolve().parent.parent

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

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.6:27b"
)

OLLAMA_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "180")
)

MAX_STUDENT_ANSWER_LENGTH = int(
    os.getenv("MAX_STUDENT_ANSWER_LENGTH", "2000")
)

MAX_HISTORY_MESSAGES = int(
    os.getenv("MAX_HISTORY_MESSAGES", "12")
)

MAX_HINT_LEVEL = 4

ALLOWED_MODELS: Set[str] = {
    "qwen3.6:27b",
    "qwen3.8:27b",
    "granite4.1:30b",
    "mistral-medium-3.5:128b"
}