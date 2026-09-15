from typing import Dict, List, Optional


class LLMError(RuntimeError):
    """Basisfehler aller LLM-Backends."""


class LLMConnectionError(LLMError):
    """Verbindung, Netzwerk, TLS oder HTTP-Fehler beim Backend."""


class LLMAuthError(LLMError):
    """Authentifizierung fehlgeschlagen oder kein API-Key gesetzt."""


class LLMRateLimitError(LLMError):
    """Rate-Limit des Backends erreicht (HTTP 429)."""


class LLMResponseError(LLMError):
    """Ungültige oder leere Antwort des Backends."""


ALLOWED_MESSAGE_ROLES = {
    "system",
    "developer",
    "user",
    "assistant",
    "tool"
}


class LLMClient:
    """Abstraktes Interface für LLM-Backends."""

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
        json_output: bool = False
    ) -> str:
        raise NotImplementedError


def validate_messages(
    messages: List[Dict[str, str]]
) -> None:
    if not messages:
        raise ValueError(
            "Die Nachrichtenliste darf nicht leer sein"
        )

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(
                "Jede Nachricht muss ein Dictionary sein"
            )

        role = message.get("role")
        content = message.get("content")

        if role not in ALLOWED_MESSAGE_ROLES:
            raise ValueError(
                f"Ungültige Nachrichtenrolle: {role}"
            )

        if not isinstance(content, str):
            raise ValueError(
                "Jede Nachricht benötigt Textinhalt"
            )
