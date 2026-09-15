import logging
from typing import Any, Dict, List, Optional

from app import config
from app.llm._http import post_json
from app.llm.base import (
    LLMClient,
    LLMResponseError,
    validate_messages
)


logger = logging.getLogger(__name__)


class OllamaNativeClient(LLMClient):
    """
    Nativer Ollama-Client (POST /api/chat)
    als lokaler Entwicklungsfallback.

    LLM_BASE_URL muss dann den Ollama-Server
    ohne /v1 enthalten,
    z.B. http://127.0.0.1:11434.
    """

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
        json_output: bool = False
    ) -> str:
        validate_messages(messages)

        payload: Dict[str, Any] = {
            "model": model or config.LLM_MODEL,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        url = (
            f"{config.LLM_BASE_URL.rstrip('/')}"
            "/api/chat"
        )

        data = post_json(
            url,
            payload,
            timeout=config.LLM_TIMEOUT
        )

        return self._extract_content(
            data,
            str(payload["model"])
        )

    @staticmethod
    def _extract_content(
        data: Dict[str, Any],
        model: str
    ) -> str:
        message = data.get("message")

        if not isinstance(message, dict):
            raise LLMResponseError(
                "In der Ollama-Antwort fehlt "
                "das Feld message"
            )

        generated_text = message.get("content")

        if (
            not isinstance(generated_text, str)
            or not generated_text.strip()
        ):
            raise LLMResponseError(
                "Ollama lieferte eine leere Chat-Antwort "
                f"Modell={model}"
            )

        return generated_text.strip()
