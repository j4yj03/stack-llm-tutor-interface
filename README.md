# KI-Tutor für Moodle-STACK-Aufgaben

Prototyp eines selbst-gehosteten LLM-Tutor-Interfaces für digitale Mathematikaufgaben mit STACK und Maxima zur symbolischen Bewertung.

## Funktionen

- **4-Stufen-Hinweis-System**: Progressive Offenlegung von Informationen (Orientierung → Strukturierung → Nächster Rechenschritt → Ausführliche Unterstützung)
- **LLM-gestützte adaptive Hinweise**: Lokales LLM generiert didaktische Hinweise basierend auf STACK-Diagnosen
- **Moodle-Integration**: Einfache Einbettung in STACK-Fragen über Feedback-Links
- **Aufgaben-Validierung**: JSON-Schema-Validierung aller Aufgabenfiles beim Serverstart
- **Chat-Verwaltung**: SQLite-basierte Speicherung von Chat-Sessions und Nachrichten
- **Tutor-Chat ohne JavaScript**: Rückfragen, sichtbarer Verlauf und weitere Hinweise über serverseitige HTML-Formulare
- **Prompt-Debugging**: Einklappbare Anzeige der tatsächlich verwendeten Rollennachrichten bei jedem LLM-Aufruf

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
| `/tutor/{chat_id}/message` | POST | HTML-Formular für Rückfragen, rendert die Tutor-Seite neu |
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

Die Einbindung erfolgt über einen Tutor-Link im Fragetext und einen
`[[javascript]]`-Sandboxblock von STACK-JS. Die nach Moodle-Zielfeld benannten
Referenzbausteine stehen in [`code/moodle/`](code/moodle/README.md):
`question_variables.txt` (Maxima), `fragetext_castext.html` (Fragetext) und
`prt_feedback.html` (passender PRT-Zweig). Es sind keine eigenständig ladbaren JS-Dateien.

Der Link überträgt neben `qid`, `diagnosis` und `ans1` die konkret
instanziierte Funktion als `funktion`. Das Backend setzt sie in den generischen
Textbaustein `question_text_template` der Aufgaben-JSON ein; Lernziele, Regeln
und Diagnosetitel sind generisch (ohne feste Zufallswerte) und bleiben auch bei
Moodle-Varianten aktiv. Die feste lokale Beispiel-Musterlösung in der JSON ist
Demodaten für lokale Tests und wird bei Varianten nie übertragen. Alternativ
akzeptiert `/start` weiterhin einen vollständigen `question_text`; beide
Parameter zusammen werden abgewiesen. Chat und Folgehints verwenden
anschließend denselben serverseitig gespeicherten Kontext.

## Tutor-Seite

Rückfragen werden per HTML-POST gesendet und ändern die Hilfestufe nicht.
„Weiterer Hinweis“ erhöht sie innerhalb derselben Session; alte Formulare dürfen
die Stufe nicht zurücksetzen. Die Seite benötigt kein JavaScript. Jeder
Generierungsversuch verbraucht einen LLM-Aufruf, also das SAIA-Rate-Limit beachten.

„Debug: erzeugter Prompt“ zeigt die Rollennachrichten **vor** der neuen Antwort,
auch bei einem fehlgeschlagenen LLM-Aufruf. Die JSON-Generierungsendpunkte liefern
dieselben Nachrichten im additiven Feld `prompt_messages`. Debug-Daten enthalten
Aufgabe und Chatverlauf: Vor produktiver Nutzung entfernen oder Zugriff beschränken.
Die Anzeige ist kein zusätzlich gespeichertes Prompt-Archiv.

Für die neuen Formulare wird `python-multipart` benötigt; die gepinnte Abhängigkeit
ist in `code/requirements.txt` enthalten. Nach einem Update Abhängigkeiten
installieren und Uvicorn neu starten, sofern kein automatischer Reload läuft.

## Forschungsprojekt

Dieses Projekt ist Teil einer Masterarbeit an der HTW Berlin:
*„Entwicklung eines KI-gestützten Tutors für Moodle-STACK-Aufgaben in mathematischen Grundlagenmodulen"*
