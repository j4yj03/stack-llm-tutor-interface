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
│   Moodle    │───▶│  FastAPI     │───▶│  Ollama/    │
│   STACK     │    │  Backend     │    │  LiteLLM    │
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
- Ollama/LiteLLM (LLM-Backend)
- SQLite (Datenbank)
- JSON Schema Draft 2020-12 (Aufgaben-Validierung)

## Voraussetzungen

- Python 3.9+
- Zugang zu einem Ollama/LiteLLM-Endpoint (z.B. HTW Berlin KI-Werkstatt)

## Installation

```bash
cd code/
pip install -r requirements.txt
```

## Umgebungskonfiguration

Erstelle eine `.env`-Datei oder setze Umgebungsvariablen:

```bash
OLLAMA_BASE_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435
OLLAMA_MODEL=qwen3.6:27b
OLLAMA_TIMEOUT=180
DATABASE_PATH=data/tutor.db
MAX_HISTORY_MESSAGES=12
```

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
# Nur Unit-Tests
pytest

# Mit Integrationstests (benötigt live LLM)
pytest -m integration
```

## Moodle-Integration

Die Einbindung erfolgt über einen erweiterten STACK-Feedback-Link in der Moodle-Frage. Siehe `moodle/`-Verzeichnis für Beispiele.

## Forschungsprojekt

Dieses Projekt ist Teil einer Masterarbeit an der HTW Berlin:
*„Entwicklung eines KI-gestützten Tutors für Moodle-STACK-Aufgaben in mathematischen Grundlagenmodulen"*