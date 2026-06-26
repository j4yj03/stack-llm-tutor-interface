import os
import requests
from typing import Optional

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:32b")


def call_ollama(prompt: str, model: Optional[str] = None) -> str:
    selected_model = model or DEFAULT_MODEL

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 220
            }
        },
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    return data.get("response", "").strip()