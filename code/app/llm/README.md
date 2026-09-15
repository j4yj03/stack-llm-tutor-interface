# Paket `code/app/llm/`

Backend-Abstraktion für alle LLM-Zugriffe. Die Tutorlogik weiß nichts
über konkrete Anbieterdetails; das Backend wird per Konfiguration gewählt.

## Aufbau

```text
__init__.py   Exporte: LLMClient, Fehlerklassen, create_llm_client
base.py       abstraktes Interface + Fehlhierarchie + Nachrichtenvalidierung
_http.py      gemeinsames requests-POST (TLS verify=True) mit Fehlerzuordnung
saia.py       OpenAI-kompatibler Client für die GWDG SAIA-Plattform
ollama.py     nativer Ollama-Client (/api/chat) als Dev-Fallback
factory.py    Backend-Wahl nach LLM_API_MODE
```

## Konfiguration (über `app.config`, gefüllt aus `.env`)

| Variable | Bedeutung | Standard |
|---|---|---|
| `LLM_API_MODE` | `saia`, Alias `litellm`/`openai`, oder `ollama` | `saia` |
| `LLM_BASE_URL` | Basis-URL; SAIA inklusive `/v1` | `https://chat-ai.academiccloud.de/v1` |
| `LLM_API_KEY` | Bearer-Token (nur lokal in `.env`) | leer |
| `LLM_MODEL` | Default-Modell | `qwen3.8-27b` |
| `LLM_TIMEOUT` | Timeout in Sekunden | `180` |
| `LLM_DISABLE_THINKING` | Reasoning unterdrücken (vLLM `chat_template_kwargs`) | `1` |

URL-Zusammensetzung:

- SAIA: `LLM_BASE_URL + "/chat/completions"` → `https://chat-ai.academiccloud.de/v1/chat/completions`
- Ollama: `LLM_BASE_URL + "/api/chat"` (Basis-URL **ohne** `/v1`, z. B. `http://127.0.0.1:11434`)

## Fehlhierarchie

```text
LLMError
├── LLMConnectionError   # Netzwerk, TLS, Timeout, sonstige HTTP-Fehler
├── LLMAuthError         # kein Key gesetzt, HTTP 401/403
├── LLMRateLimitError    # HTTP 429, liest Retry-After (SAIA: ~100 Calls/h)
└── LLMResponseError     # leere/ungültige Antwort, ungültiges JSON
```

`main.py` mappt: `LLMRateLimitError` → HTTP 429, alle anderen `LLMError` → HTTP 502.

## Verwendung

```python
from app.llm import create_llm_client

client = create_llm_client()          # nach LLM_API_MODE
answer = client.chat(
    messages=[{"role": "user", "content": "..."}],
    model="qwen3.8-27b",              # optional, sonst LLM_MODEL
    temperature=0.2,
    max_tokens=400,
)
```

Funktionale Einschränkungen: alle Clients validieren Nachrichtenrollen
(`system`, `developer`, `user`, `assistant`, `tool`), kürzen Fehlerausgaben
auf 1000 Zeichen, loggen niemals den API-Key und senden mit `verify=True`.

## Eigene Backends ergänzen

1. Neue Datei im Paket mit Klasse `...(LLMClient)` und Implementierung von `chat()`.
2. Modus-Alias in `factory.py` registrieren.
3. Unit-Tests mit gemocktem `app.llm._http.SESSION` ergänzen (Happy Path + Fehlerklassen).
4. `ALLOWED_MODELS` bzw. `LLM_ALLOWED_MODELS` für die Zielplattform pflegen.
