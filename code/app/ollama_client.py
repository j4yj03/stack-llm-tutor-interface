"""Kompatibilitäts-Wrapper für die bisherige Modul-API.

Die Implementierung lebt jetzt in ``app.llm``;
die Funktionen delegieren an die Backend-Fabrik.
Die Namen bleiben aus Kompatibilitätsgründen bestehen.
"""

from typing import Dict, List, Optional

from app.llm import LLMError, create_llm_client


# Alter Fehlername bleibt verfügbar.
OllamaClientError = LLMError


def call_ollama_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 400,
    json_output: bool = False
) -> str:
    return create_llm_client().chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_output=json_output
    )


def call_ollama_generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 400,
    json_output: bool = False
) -> str:
    messages: List[Dict[str, str]] = [
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
    return call_ollama_generate(
        prompt=prompt,
        model=model
    )
