"""

qwen3.6:27b bietet Completion, Tool-Nutzung und Thinking, hat 27,8 Milliarden Parameter und ein Kontextfenster von 262.144 Tokens. 
Damit ist es ein guter Kompromiss aus Qualität, mathematischem Reasoning und Antwortzeit.
Als größeres Vergleichsmodell eignet sich mistral-medium-3.5:128b. Es unterstützt ebenfalls Completion, Tools und Thinking, ist mit 127,7 Milliarden Parametern aber deutlich ressourcenintensiver.

"""

import os
from typing import Any, Dict, List, Optional

import requests


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
)

DEFAULT_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.6:27b"
)

REQUEST_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "180")
)


class OllamaClientError(RuntimeError):
    """Fehler beim Zugriff auf die Ollama-API."""


def _post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            verify=True
        )
        response.raise_for_status()
    except requests.exceptions.SSLError as exc:
        raise OllamaClientError(
            f"SSL-Fehler beim Zugriff auf {url}. "
            "Das Zertifikat sollte nicht durch verify=False umgangen werden."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise OllamaClientError(
            f"Zeitüberschreitung beim Zugriff auf {url}."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise OllamaClientError(
            f"Keine Verbindung zur Ollama-API unter {url} möglich."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        body = response.text[:1000]
        raise OllamaClientError(
            f"Ollama antwortete mit HTTP {response.status_code}: {body}"
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise OllamaClientError(
            f"Ollama lieferte keine gültige JSON-Antwort: "
            f"{response.text[:1000]}"
        ) from exc


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

    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
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

    return generated_text.strip()


def call_ollama_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 300,
    json_output: bool = False
) -> str:
    """
    Ruft POST /api/chat auf.

    messages muss beispielsweise so aussehen:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ]
    """

    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
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

    message = data.get("message", {})
    generated_text = message.get("content")

    if not isinstance(generated_text, str):
        raise OllamaClientError(
            "In der Ollama-Antwort fehlt das Feld 'message.content'."
        )

    return generated_text.strip()


def call_ollama(
    prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Kompatibilitätsfunktion für den bisherigen Code.
    Verwendet standardmäßig /api/generate.
    """

    return call_ollama_generate(
        prompt=prompt,
        model=model
    )