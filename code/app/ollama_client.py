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
    """
    Fehler beim Zugriff auf den LiteLLM-Proxy.

    Der Klassenname bleibt aus Kompatibilitätsgründen bestehen.
    """


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
            "LiteLLM lieferte keine gültige JSON-Antwort: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    if not isinstance(data, dict):
        raise OllamaClientError(
            "LiteLLM lieferte kein JSON-Objekt"
        )

    return data


def _post(
    endpoint: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    url = (
        f"{OLLAMA_BASE_URL.rstrip('/')}/"
        f"{endpoint.lstrip('/')}"
    )

    print(f"LiteLLM POST URL: {url}")
    print(f"LiteLLM Modell: {payload.get('model')}")

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
            "Keine Verbindung zur LiteLLM-API "
            f"unter {url} möglich"
        ) from exc

    except requests.exceptions.HTTPError as exc:
        raise OllamaClientError(
            f"POST {url} antwortete mit HTTP "
            f"{response.status_code} "
            f"Modell={payload.get('model')} "
            f"Antwort={response.text[:MAX_ERROR_BODY_LENGTH]}"
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
        "developer",
        "user",
        "assistant",
        "tool"
    }

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(
                "Jede Nachricht muss ein Dictionary sein"
            )

        role = message.get("role")
        content = message.get("content")

        if role not in allowed_roles:
            raise ValueError(
                f"Ungültige Nachrichtenrolle: {role}"
            )

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
    """
    Ruft den OpenAI-kompatiblen Chat-Completion-Endpunkt
    des LiteLLM-Proxys auf.

    Der Funktionsname bleibt aus Kompatibilitätsgründen bestehen.
    """

    _validate_messages(messages)

    payload: Dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    if json_output:
        payload["response_format"] = {
            "type": "json_object"
        }

    data = _post(
        "/v1/chat/completions",
        payload
    )

    choices = data.get("choices")

    if not isinstance(choices, list) or not choices:
        raise OllamaClientError(
            "In der LiteLLM-Antwort fehlt "
            "das Feld choices"
        )

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise OllamaClientError(
            "Der erste LiteLLM-Choice ist ungültig"
        )

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise OllamaClientError(
            "In der LiteLLM-Antwort fehlt "
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

        raise OllamaClientError(
            "LiteLLM lieferte eine leere Chat-Antwort "
            f"finish_reason={finish_reason}"
        )

    return generated_text.strip()


def call_ollama_generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 400,
    json_output: bool = False
) -> str:
    """
    Kompatibilitätsfunktion für bisherige Generate-Aufrufe.

    Der einzelne Prompt wird intern als User-Nachricht
    an /v1/chat/completions gesendet.
    """

    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    return call_ollama_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_output=json_output
    )


def call_ollama(
    prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Rückwärtskompatible Hilfsfunktion.
    """

    return call_ollama_generate(
        prompt=prompt,
        model=model
    )