# Paket `code/app/llm/`

Stand: 2026-10-02. Providerabstraktion, nicht die Quelle didaktischer Regeln.
Serversteuerung: [../README.md](../README.md); vollstaendige Parameter:
[../../config/README.md](../../config/README.md); kontrollierter Clientpfad:
[../../evaluation/README.md](../../evaluation/README.md).

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
| `LLM_DISABLE_THINKING` | SAIA `chat_template_kwargs` bzw. Ollama `think=not LLM_DISABLE_THINKING` | `1` |
| `LLM_TEMPERATURE` | Tutor-Temperatur, endlich `0..2` | `0.2` |
| `LLM_MAX_TOKENS` | Tutor-Tokenlimit, Ganzzahl `1..32768` | `400` |
| `LLM_RETRY_DELAY` | Nichtnegative endliche Wartezeit vor SAIA-Fallback | `2` |

Das Clientinterface hat weiterhin Defaultargumente `temperature=0.2`,
`max_tokens=400`, `json_output=False`; die Tutororchestrierung uebergibt
explizit die aktuellen Konfigurationswerte. Individuelle Startwahl nutzt
dieselben Generatorparameter und verlangt JSON. Der optionale Judge
uebergibt separat `EVALUATION_JUDGE_TEMPERATURE=0.0` und
`EVALUATION_JUDGE_MAX_TOKENS=1200`, ebenfalls JSON, sowie einen expliziten
Judgealias. Diese Werte sind Requestparameter, keine gemessenen Providerinternas.

URL-Zusammensetzung:

- SAIA: `LLM_BASE_URL + "/chat/completions"` → `https://chat-ai.academiccloud.de/v1/chat/completions`
- Ollama: `LLM_BASE_URL + "/api/chat"` (Basis-URL **ohne** `/v1`, z. B. `http://127.0.0.1:11434`)

Der native Ollamaclient uebertraegt `think=not LLM_DISABLE_THINKING` statt
eines fest verdrahteten `false`. Bei `json_output=True` setzt er
`format="json"`; andernfalls fehlt dieses Feld. Temperatur/Tokenlimit gehen
als `options.temperature`/`options.num_predict` an Ollama. Strukturierte
Start-/Tutor-/Judgeantworten nutzen damit auch im lokalen Backend JSONmodus;
die serverseitige Validierung bleibt erforderlich.

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
from app import config
from app.llm import create_llm_client

client = create_llm_client()          # nach LLM_API_MODE
answer = client.chat(
    messages=[{"role": "user", "content": "..."}],
    model=config.LLM_MODEL,
    temperature=config.LLM_TEMPERATURE,
    max_tokens=config.LLM_MAX_TOKENS,
    json_output=config.TUTOR_RESPONSE_FORMAT == "structured",
)
```

Funktionale Einschränkungen: alle Clients validieren Nachrichtenrollen
(`system`, `developer`, `user`, `assistant`, `tool`), kürzen Fehlerausgaben
auf 1000 Zeichen, loggen niemals den API-Key und senden mit `verify=True`.

Das obige Beispiel macht bei Ausfuehrung einen echten Provideraufruf und ist
kein Offlinecheck. Evaluation importiert keinen Providerclient; sie nutzt
Tutor-/Judge-API mit eigenem Live-Gate. Providerkeys bleiben auf dem Server;
`X-Evaluation-Token` ist nur der gesonderte Evaluationzugang, kein Upstreamkey.

## Operationsvertrag

Ein fester oder expliziter Start braucht eine Hintoperation; individuelle
Startwahl zuerst eine Auswahloperation und dann den Hint. Stage 0 ist eine
diagnostische Antwort desselben Promptpfads, kein separater Providerbackend.
Adaption entscheidet erst bei einer Folgeinteraktion; sie startet keinen Timer
und erzeugt allein keine neue LLM-Operation.

Der SAIA-Client kann nach `LLMConnectionError` einmal ohne
`chat_template_kwargs` versuchen, sofern das Feld enthalten war.
`LLM_RETRY_DELAY` gilt auch in dieser Auswahl-/Judgeoperation. Mit
`LLM_DISABLE_THINKING=0` fehlt das Feld und der Fallback entfaellt.
Requested Thinking-Unterdrueckung ist kein Nachweis effektiven Thinkingmodus.

Deshalb reserviert das Evaluationsbudget konservativ 4 Einheiten fuer einen
Generatorrequest und 2 fuer einen Judge, nicht exakt beobachtete Calls.
Logische `llm_operations` in der Tutorantwort ist keine Tokenusage oder
Upstreamattemptzahl. Der Public-Snapshot enthaelt angeforderte Parameter,
Timeout und Retrydelay, aber keine Providerkeys, Upstream-URL oder Allowlist.
Providerrequest-/Modell-IDs, Modelldigest, Finishreason, Token und wirksame
Thinkingkonfiguration werden vom aktuellen API-Vertrag nicht beobachtet.

Strukturiertes Tutor-/Judge-JSON wird nach Providerantwort serverseitig
validiert; ein gesetztes `json_output` garantiert keine semantisch korrekten
Diagnosen oder mathematische Verifizierung. Tests mocken `_http.SESSION`;
Integrationstests nur nach expliziter Freigabe ausfuehren.

## Eigene Backends ergänzen

1. Neue Datei im Paket mit Klasse `...(LLMClient)` und Implementierung von `chat()`.
2. Modus-Alias in `factory.py` registrieren.
3. Unit-Tests mit gemocktem `app.llm._http.SESSION` ergänzen (Happy Path + Fehlerklassen).
4. `ALLOWED_MODELS` bzw. `LLM_ALLOWED_MODELS` für die Zielplattform pflegen.
