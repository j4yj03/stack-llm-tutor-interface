import json
from typing import Any, Dict, List, Optional

import requests
from requests import Response
from requests.adapters import HTTPAdapter

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT
)


MAX_ERROR_BODY_LENGTH = 1000


class OllamaClientError(RuntimeError):
    """Fehler beim Zugriff auf die Ollama-API."""


SESSION = requests.Session()
SESSION.mount(
    "https://",
    HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=0
    )
)


def _parse_json_response(
    response: Response
) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaClientError(
            "Ollama lieferte keine gültige "
            "JSON-Antwort: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    if not isinstance(data, dict):
        raise OllamaClientError(
            "Ollama lieferte kein JSON-Objekt"
        )

    return data


def _post(
    endpoint: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    url = (
        f"{OLLAMA_BASE_URL}/"
        f"{endpoint.lstrip('/')}"
    )

    try:
        response = SESSION.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
            verify=True
        )
        response.raise_for_status()

    except requests.exceptions.SSLError as exc:
        raise OllamaClientError(
            f"SSL-Fehler beim Zugriff auf {url}"
        ) from exc

    except requests.exceptions.Timeout as exc:
        raise OllamaClientError(
            "Zeitüberschreitung nach "
            f"{OLLAMA_TIMEOUT} Sekunden"
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise OllamaClientError(
            "Keine Verbindung zur Ollama-API "
            f"unter {url} möglich"
        ) from exc

    except requests.exceptions.HTTPError as exc:
        raise OllamaClientError(
            "Ollama antwortete mit HTTP "
            f"{response.status_code}: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise OllamaClientError(
            f"Unerwarteter Netzwerkfehler: {exc}"
        ) from exc

    return _parse_json_response(response)


def _validate_messages(
    messages: List[Dict[str, str]]
) -> None:
    if not messages:
        raise ValueError(
            "Die Nachrichtenliste darf nicht leer sein"
        )

    allowed_roles = {
        "system",
        "user",
        "assistant",
        "tool"
    }

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(
                "Jede Nachricht muss ein Dictionary sein"
            )

        if message.get("role") not in allowed_roles:
            raise ValueError(
                "Ungültige Nachrichtenrolle: "
                f"{message.get('role')}"
            )

        content = message.get("content")

        if not isinstance(content, str):
            raise ValueError(
                "Jede Nachricht benötigt Textinhalt"
            )


def call_ollama_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 400,
    json_output: bool = False
) -> str:
    _validate_messages(messages)

    payload: Dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }

    if json_output:
        payload["format"] = "json"

    data = _post(
        "/api/chat",
        payload
    )

    message = data.get("message")

    if not isinstance(message, dict):
        raise OllamaClientError(
            "In der Ollama-Antwort fehlt "
            "das Objekt message"
        )

    generated_text = message.get("content")

    if (
        not isinstance(generated_text, str)
        or not generated_text.strip()
    ):
        thinking = message.get(
            "thinking",
            data.get("thinking")
        )

        if (
            isinstance(thinking, str)
            and thinking.strip()
        ):
            raise OllamaClientError(
                "Das Modell lieferte nur Thinking-Inhalt "
                "aber keine finale Antwort"
            )

        raise OllamaClientError(
            "Ollama lieferte eine leere Chat-Antwort "
            f"vorhandene Felder={list(data.keys())}"
        )

    return generated_text.strip()


def call_ollama_generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 400,
    json_output: bool = False
) -> str:
    payload: Dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }

    if json_output:
        payload["format"] = "json"

    data = _post(
        "/api/generate",
        payload
    )

    generated_text = data.get("response")

    if (
        not isinstance(generated_text, str)
        or not generated_text.strip()
    ):
        raise OllamaClientError(
            "Ollama lieferte keine finale Textantwort "
            f"vorhandene Felder={list(data.keys())}"
        )

    return generated_text.strip()


def call_ollama(
    prompt: str,
    model: Optional[str] = None
) -> str:
    return call_ollama_generate(
        prompt=prompt,
        model=model
    )