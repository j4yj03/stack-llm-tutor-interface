import logging
from typing import Any, Dict, List, Optional

from app import config
from app.llm._http import post_json
from app.llm.base import (
    LLMAuthError,
    LLMClient,
    LLMResponseError,
    validate_messages
)


logger = logging.getLogger(__name__)


class SAIClient(LLMClient):
    """
    OpenAI-kompatibler Client für die GWDG
    SAIA-Plattform (Scalable AI Accelerator).

    Ruft POST {LLM_BASE_URL}/chat/completions auf.
    LLM_BASE_URL enthält die API-Version,
    z.B. https://chat-ai.academiccloud.de/v1.
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

        api_key = config.LLM_API_KEY

        if not api_key:
            raise LLMAuthError(
                "Kein API-Key gesetzt: LLM_API_KEY "
                "fehlt in der lokalen code/.env. "
                "Eigene Keys gibt es unter "
                "https://saia.gwdg.de/dashboard"
            )

        payload: Dict[str, Any] = {
            "model": model or config.LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if json_output:
            payload["response_format"] = {
                "type": "json_object"
            }

        # vLLM-typische Option: Reasoning unterdrücken,
        # damit das Token-Budget dem Hinweis zugutekommt.
        if config.LLM_DISABLE_THINKING:
            payload["chat_template_kwargs"] = {
                "enable_thinking": False
            }

        url = (
            f"{config.LLM_BASE_URL.rstrip('/')}"
            "/chat/completions"
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        data = post_json(
            url,
            payload,
            headers=headers,
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
        choices = data.get("choices")

        if (
            not isinstance(choices, list)
            or not choices
        ):
            raise LLMResponseError(
                "In der SAIA-Antwort fehlt "
                "das Feld choices"
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise LLMResponseError(
                "Der erste SAIA-Choice ist ungültig"
            )

        message = first_choice.get("message")

        if not isinstance(message, dict):
            raise LLMResponseError(
                "In der SAIA-Antwort fehlt "
                "choices[0].message"
            )

        generated_text = message.get("content")

        if (
            not isinstance(generated_text, str)
            or not generated_text.strip()
        ):
            finish_reason = first_choice.get(
                "finish_reason"
            )

            raise LLMResponseError(
                "SAIA lieferte eine leere Chat-Antwort "
                f"Modell={model} "
                f"finish_reason={finish_reason}"
            )

        return generated_text.strip()
