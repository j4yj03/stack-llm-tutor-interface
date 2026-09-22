# Anwendungsordner `code/`

Prototyp der FastAPI-Anwendung des KI-Tutors für Moodle-STACK-Aufgaben.

## Struktur

```text
code/
├── app/            FastAPI-Anwendung (Entrypoint, Module, Templates)
│   ├── llm/        Backend-Abstraktion für LLM-Zugriffe (saia, ollama)
│   ├── templates/  Jinja2-Templates (Tutor-Seite)
│   ├── main.py     FastAPI-Entrypoint mit allen REST-Endpunkten
│   ├── config.py   Zentrale Konfiguration (Pfade, LLM, Limits)
│   ├── schemas.py  Pydantic-Anfrage- und Antwortmodelle
│   ├── database.py SQLite-Schemainitialisierung
│   ├── chat_store.py        Chat-/Nachrichtenpersistenz (UUID-Sessions)
│   ├── hint_policy.py       Laden und Validieren der generischen Hilfestufen
│   ├── prompt_builder.py    Erzeugt rollenbasierte LLM-Nachrichten
│   ├── task_loader.py       Lädt und validiert tasks/*.json gegen das Schema
│   └── ollama_client.py     Kompatibilitäts-Wrapper zu app.llm
├── config/         Generische Hilfestufen-Policy (hint_levels.json)
├── data/           SQLite-Datenbank (tutor.db, nicht committet)
├── moodle/         Moodle/STACK-Integrationsbausteine (siehe moodle/README.md)
├── schemas/        JSON-Schema für Aufgaben-Definitionen
├── tasks/          Lokale Aufgaben-Definitionen
├── evaluation/     Evaluations-Suite (fachliche Tutor-API-Tests, siehe evaluation/README.md)
├── tests/          Pytest-Suite
├── .env            Lokale Secrets (niemals committen)
├── .env.example    Vorlage ohne Secrets
└── pytest.ini      pytest-Konfiguration (integration-Marker)
```

## Setup

```bash
cd code/
pip install -r requirements.txt
cp .env.example .env   # dann API-Key eintragen
```

## Starten

```bash
python -m uvicorn app.main:app --reload --port 8000
```

API-Dokumentation: `http://127.0.0.1:8000/docs`

## Tests

```bash
pytest -m "not integration" -v   # Unit-Tests ohne LLM-Zugang
pytest -m integration -v         # Integrationstests (braucht API-Key in .env)
```

## Evaluation (fachliche Test-Suite)

Der Ordner `evaluation/` enthält eine separate, reproduzierbare Suite für
fachliche Tutor-Experimente: Testaufgaben × Kontextprofile führen zu
echten `POST /api/tutor/start`-Aufrufen, auswertbaren Ergebnissen und
einem Jupyter-Notebook zur Offline-Analyse. Bedienung, Regeln
(Live-Gate `--execute-live`, Budget, Versuchsjournal) und Zielformate:
`evaluation/README.md` und `docs/evaluation_protocol.md`.

## Wichtige Regeln

- `.env` enthält den SAIA-API-Key und wird durch `.gitignore` vom Commit ausgeschlossen.
- Ungültige Task-JSON-Dateien verhindern bewusst den Serverstart (Fail-fast).
- STACK/PRT bleiben die maßgebliche mathematische Bewertungsinstanz; das LLM formuliert nur Hinweise.
