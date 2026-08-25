"""
Client für die Ollama-API der HTW Berlin.

Standardmodell:
qwen3.6:27b

Das Modell unterstützt Completion, Tool-Nutzung und Thinking.
Es besitzt 27,8 Milliarden Parameter und ein Kontextfenster
von 262.144 Tokens.
"""

import os
from typing import Any, Dict, List, Optional

import requests
from requests import Response
from requests.adapters import HTTPAdapter


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
).rstrip("/")

DEFAULT_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.6:27b"
)

REQUEST_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "180")
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


def _parse_json_response(response: Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaClientError(
            "Ollama lieferte keine gültige JSON-Antwort: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    if not isinstance(data, dict):
        raise OllamaClientError(
            "Ollama lieferte kein JSON-Objekt."
        )

    return data


def _post(
    endpoint: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/{endpoint.lstrip('/')}"

    try:
        response = SESSION.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            verify=True
        )
        response.raise_for_status()

    except requests.exceptions.SSLError as exc:
        raise OllamaClientError(
            f"SSL-Fehler beim Zugriff auf {url}. "
            "Die Zertifikatsprüfung sollte nicht durch "
            "verify=False deaktiviert werden."
        ) from exc

    except requests.exceptions.Timeout as exc:
        raise OllamaClientError(
            f"Zeitüberschreitung nach {REQUEST_TIMEOUT} Sekunden "
            f"beim Zugriff auf {url}."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise OllamaClientError(
            f"Keine Verbindung zur Ollama-API unter {url} möglich."
        ) from exc

    except requests.exceptions.HTTPError as exc:
        raise OllamaClientError(
            f"Ollama antwortete mit HTTP {response.status_code}: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise OllamaClientError(
            f"Unerwarteter Netzwerkfehler beim Zugriff auf {url}: {exc}"
        ) from exc

    return _parse_json_response(response)


def call_ollama_generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 300,
    json_output: bool = False
) -> str:
    """
    Ruft POST /api/generate auf und gibt den erzeugten Text zurück.
    """

    selected_model = model or DEFAULT_MODEL

    payload: Dict[str, Any] = {
        "model": selected_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }

    if json_output:
        payload["format"] = "json"

    data = _post("/api/generate", payload)
    generated_text = data.get("response")

    if not isinstance(generated_text, str):
        raise OllamaClientError(
            "In der Ollama-Antwort fehlt das Textfeld 'response'."
        )

    generated_text = generated_text.strip()

    if not generated_text:
        raise OllamaClientError(
            "Ollama lieferte eine leere Antwort."
        )

    return generated_text


def call_ollama_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 300,
    json_output: bool = False
) -> str:
    """
    Ruft POST /api/chat auf.

    Beispiel für messages:

    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ]
    """

    if not messages:
        raise ValueError(
            "Die Nachrichtenliste darf nicht leer sein."
        )

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(
                "Jede Nachricht muss ein Dictionary sein."
            )

        if message.get("role") not in {
            "system",
            "user",
            "assistant",
            "tool"
        }:
            raise ValueError(
                f"Ungültige Nachrichtenrolle: {message.get('role')}"
            )

        if not isinstance(message.get("content"), str):
            raise ValueError(
                "Jede Nachricht benötigt einen Textinhalt."
            )

    selected_model = model or DEFAULT_MODEL

    payload: Dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }

    if json_output:
        payload["format"] = "json"

    data = _post("/api/chat", payload)

    message = data.get("message")

    if not isinstance(message, dict):
        raise OllamaClientError(
            "In der Ollama-Antwort fehlt das Objekt 'message'."
        )

    generated_text = message.get("content")

    if not isinstance(generated_text, str):
        raise OllamaClientError(
            "In der Ollama-Antwort fehlt das Feld 'message.content'."
        )

    generated_text = generated_text.strip()

    if not generated_text:
        raise OllamaClientError(
            "Ollama lieferte eine leere Chat-Antwort."
        )

    return generated_text


def call_ollama(
    prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Kompatibilitätsfunktion für den bisherigen Code.

    Verwendet standardmäßig POST /api/generate.
    """

    return call_ollama_generate(
        prompt=prompt,
        model=model,
        temperature=0.2,
        max_tokens=300
    )