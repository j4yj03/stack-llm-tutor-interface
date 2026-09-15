from typing import Optional

from app import config
from app.llm.base import LLMClient, LLMError
from app.llm.ollama import OllamaNativeClient
from app.llm.saia import SAIClient


# litellm/openai sind Aliase für den
# OpenAI-kompatiblen SAIClient.
SAIA_MODE_ALIASES = {"saia", "litellm", "openai"}

OLLAMA_MODE_ALIASES = {"ollama"}


def create_llm_client(
    mode: Optional[str] = None
) -> LLMClient:
    """
    Wählt das LLM-Backend nach LLM_API_MODE
    (oder explizitem mode).
    """

    selected = (
        mode
        or config.LLM_API_MODE
    )

    if isinstance(selected, str):
        selected = selected.strip().lower()

    if selected in SAIA_MODE_ALIASES:
        return SAIClient()

    if selected in OLLAMA_MODE_ALIASES:
        return OllamaNativeClient()

    raise LLMError(
        "Unbekannter LLM_API_MODE: "
        f"{selected!r}. "
        "Erlaubt: saia, ollama"
    )
