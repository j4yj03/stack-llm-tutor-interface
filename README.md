# KI-Tutor für Moodle-STACK-Aufgaben

Prototyp eines selbst-gehosteten LLM-Tutor-Interfaces für digitale Mathematikaufgaben mit STACK und Maxima zur symbolischen Bewertung.

## Funktionen

- **4-Stufen-Hinweis-System**: Progressive Offenlegung von Informationen (Orientierung → Strukturierung → Nächster Rechenschritt → Ausführliche Unterstützung)
- **LLM-gestützte adaptive Hinweise**: Lokales LLM generiert didaktische Hinweise basierend auf STACK-Diagnosen
- **Moodle-Integration**: Einfache Einbettung in STACK-Fragen über Feedback-Links
- **Aufgaben-Validierung**: JSON-Schema-Validierung aller Aufgabenfiles beim Serverstart
- **Chat-Verwaltung**: SQLite-basierte Speicherung von Chat-Sessions und Nachrichten

## Architektur

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Moodle    │───▶│  FastAPI     │───▶│  GWDG SAIA/ │
│   STACK     │    │  Backend     │    │  Ollama     │
└─────────────┘    └──────────────┘    └─────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   SQLite     │
                   │   Datenbank  │
                   └──────────────┘
```

**Technologien:**
- Python 3.9+, FastAPI, Uvicorn
- Jinja2 (Templating), Pydantic (Validierung)
- SAIA (GWDG, OpenAI-kompatibel) oder nativer Ollama-Server (LLM-Backend, austauschbar)
- SQLite (Datenbank)
- JSON Schema Draft 2020-12 (Aufgaben-Validierung)

## Voraussetzungen

- Python 3.9+
- LLM-Zugang:
  - **GWDG SAIA** (Standard): API-Key über https://saia.gwdg.de/dashboard anfordern
  - **Lokaler Ollama-Server** als Entwicklungsfallback

## Installation

```bash
cd code/
pip install -r requirements.txt
```

## Umgebungskonfiguration

Kopiere `.env.example` zu `.env` (wird nicht committet) und setze den API-Key:

```bash
cp .env.example .env
```

```env
LLM_API_MODE=saia
LLM_BASE_URL=https://chat-ai.academiccloud.de/v1
LLM_API_KEY=<eigener SAIA-Key>
LLM_MODEL=qwen3.8-27b
LLM_TIMEOUT=180
DATABASE_PATH=data/tutor.db
MAX_HISTORY_MESSAGES=12
```

Wichtige Hinweise:

- Der API-Key darf **niemals** committet werden (`.env` ist via `.gitignore` ausgeschlossen)
- Rate-Limit von SAIA: maximal ~100 Aufrufe pro Stunde beachten
- `LLM_DISABLE_THINKING=1` (Standard) unterdrückt das Reasoning der Modelle und spart Token-Budget
- Lokaler Ollama-Fallback: `LLM_API_MODE=ollama` und `LLM_BASE_URL=http://127.0.0.1:11434`
- Aktuelle Modellliste: `GET https://chat-ai.academiccloud.de/v1/models` (mit Bearer-Key)

## Starten

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API-Endpunkte

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/health` | GET | Health-Check |
| `/tasks` | GET | Liste aller verfügbaren Aufgaben |
| `/start` | GET | Tutor-Hauptseite (aus Moodle) |
| `/api/tutor/start` | POST | Tutor-Session starten |
| `/api/tutor/{chat_id}/next-hint` | POST | Nächsten Hinweis anfordern |
| `/api/tutor/{chat_id}/message` | POST | Nachricht im Chat senden |
| `/api/tutor/{chat_id}/history` | GET | Chat-Verlauf abrufen |

## Testen

```bash
# Nur Unit-Tests (ohne LLM-Zugang)
pytest -m "not integration"

# Mit Integrationstests (benötigt API-Key in .env)
pytest -m integration
```

## Moodle-Integration

Die Einbindung erfolgt über einen erweiterten STACK-Feedback-Link in der Moodle-Frage. Siehe `moodle/`-Verzeichnis für Beispiele.

## Forschungsprojekt

Dieses Projekt ist Teil einer Masterarbeit an der HTW Berlin:
*„Entwicklung eines KI-gestützten Tutors für Moodle-STACK-Aufgaben in mathematischen Grundlagenmodulen"*