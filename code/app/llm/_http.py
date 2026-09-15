import logging
from typing import Any, Dict, Optional

import requests
from requests import Response
from requests.adapters import HTTPAdapter

from app.llm.base import (
    LLMAuthError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError
)


logger = logging.getLogger(__name__)

MAX_ERROR_BODY_LENGTH = 1000

SESSION = requests.Session()
SESSION.mount(
    "https://",
    HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=0
    )
)


def parse_json_response(
    response: Response
) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMResponseError(
            "Das Backend lieferte keine gültige "
            "JSON-Antwort: "
            f"{response.text[:MAX_ERROR_BODY_LENGTH]}"
        ) from exc

    if not isinstance(data, dict):
        raise LLMResponseError(
            "Das Backend lieferte kein JSON-Objekt"
        )

    return data


def _raise_for_http_error(
    response: Response,
    url: str
) -> None:
    status = response.status_code

    if status in (401, 403):
        raise LLMAuthError(
            "Authentifizierung fehlgeschlagen: "
            f"HTTP {status} von {url}. "
            "API-Key prüfen (LLM_API_KEY). "
            f"Antwort={response.text[:MAX_ERROR_BODY_LENGTH]}"
        )

    if status == 429:
        retry_after = response.headers.get(
            "Retry-After",
            "unbekannt"
        )

        raise LLMRateLimitError(
            "Rate-Limit erreicht: HTTP 429 von "
            f"{url}. "
            f"Retry-After={retry_after}. "
            "Bitte kurze Zeit warten."
        )

    raise LLMConnectionError(
        f"POST {url} antwortete mit HTTP "
        f"{status} "
        f"Antwort={response.text[:MAX_ERROR_BODY_LENGTH]}"
    )


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 180
) -> Dict[str, Any]:
    logger.info(
        "LLM-POST %s (Modell=%s)",
        url,
        payload.get("model")
    )

    try:
        response = SESSION.post(
            url,
            json=payload,
            headers=headers or {},
            timeout=timeout,
            verify=True
        )
        response.raise_for_status()

    except requests.exceptions.SSLError as exc:
        raise LLMConnectionError(
            f"SSL-Fehler beim Zugriff auf {url}"
        ) from exc

    except requests.exceptions.Timeout as exc:
        raise LLMConnectionError(
            "Zeitüberschreitung nach "
            f"{timeout} Sekunden"
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise LLMConnectionError(
            f"Keine Verbindung unter {url} möglich"
        ) from exc

    except requests.exceptions.HTTPError as exc:
        _raise_for_http_error(response, url)

    except requests.exceptions.RequestException as exc:
        raise LLMConnectionError(
            f"Unerwarteter Netzwerkfehler: {exc}"
        ) from exc

    return parse_json_response(response)
