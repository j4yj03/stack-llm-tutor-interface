# Empfehlungen: Alternative LLM-APIs nach Abschaltung der Hochschul-Ollama-API

## Kontext

Der Betreiber der Hochschul-Infrastruktur hat mitgeteilt, dass die native
**Ollama-API am 01.09.2026 abgeschaltet wird**. Tests müssen bis dahin
abgeschlossen oder Pipelines auf andere APIs umgestellt werden.

Der aktuelle Fehler unseres Tutors (`HTTP 401` mit
`"No api key passed in."` bei
`POST https://f2ki-h100-1.f2.htw-berlin.de:11435/v1/chat/completions`) zeigt,
dass der Host zwar noch erreichbar ist, der Zugang jetzt aber einen
**API-Key** verlangt statt wie zuvor tokenlos zu funktionieren. Das deutet
auf eine **OpenAI-kompatible, authentifizierte** Schnittstelle (z. B.
LiteLLM) hin.

## Randbedingungen (aus AGENTS.md)

- STACK bleibt die autoritative mathematische Bewertungskomponente
- LLM-Backends müssen austauschbar sein
- **API-Keys dürfen nie committet werden** (nur über Env-Variablen,
  lokale `.env`, Docker-Secrets, n8n-Credentials, Secret-Store)
- TLS-Zertifikatsprüfung bleibt aktiv (`verify=True`)
- Der Zugriff auf externe Dienste wird in Unit-Tests gemockt
- Es werden echte Studierendenantworten verarbeitet → Datenschutz prüfen

## Kurzüberblick der Optionen

| Option | Benötigt Key | Datenschutz | Aufwand | Anmerkung |
|---|---:|---:|---:|---|
| HS-Host mit gültigem Key (LiteLLM, OpenAI-kompatibel) | ja | vom HS verwaltet | sehr gering | nur `OLLAMA_API_KEY` setzen |
| Lokales Ollama | nein | sehr gut (lokal) | gering | sofort nutzbar, Fallback |
| Lokale Server-LLMs (vLLM / llama.cpp) | nein | sehr gut (lokal) | mittel | OpenAI-kompatible API |
| Kommerzielle Anbieter (OpenAI, Azure, OpenRouter, Anthropic-Gateway) | ja | extern, klärungsbedürftig | gering | bequem, ggf. DSGVO/Personenbezug prüfen |

## Empfohlene Vorgehensweise

1. **Gültigen Key für den bestehenden HS-Host anfragen** (falls verfügbar).
   Damit wäre der Umbau minimal: nur `OLLAMA_API_KEY` in der Umgebung bzw.
   `code/.env` setzen. Der Code (siehe unten) ist dafür bereits vorbereitet.
2. **Gleichzeitig lokales Ollama als development-Fallback einsetzen**, damit
   das Projekt ohne externe Abhängigkeit und ohne Key weiterläuft.
3. Den tatsächlichen Endpunkt-/Auth-Vertrag vom Betreiber dokumentieren
   lassen, sobald klar ist, welche Schnittstelle final gilt.

## Bereits umgesetzte Code-Anpassungen

- `code/app/config.py`:
  - lädt `code/.env` über `python-dotenv`
  - liest `OLLAMA_API_KEY` aus der Umgebung
- `code/app/ollama_client.py`:
  - sendet `Authorization: Bearer <key>` an
    `/v1/chat/completions`, wenn `OLLAMA_API_KEY` gesetzt ist
- `code/requirements.txt`:
  - `python-dotenv` ergänzt

Hinweis: Ohne gültigen Key bleibt es bei `HTTP 401`. Einen Key nicht
erfinden (siehe AGENTS.md: „Do not work around this by inventing a token").

## Konfigurationsbeispiele

### 1) HS-Host mit Key (OpenAI-kompatibel / LiteLLM)

```dotenv
OLLAMA_BASE_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435
OLLAMA_MODEL=qwen3.6:27b
OLLAMA_API_KEY=<dein-echter-key>
OLLAMA_TIMEOUT=180
```

### 2) Lokales Ollama (Fallback, kein Key)

```cmd
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen3:8b
python -m uvicorn app.main:app --reload --port 8000
```

Davon abgesehen empfiehlt sich die in AGENTS.md geplante Abstraktion in
`app/llm/` (basierte `LLMClient`-Schnittstelle mit `OllamaClient` und
`LiteLLMClient`), um Backends sauber und ohne Code-Duplikation zu wechseln.
