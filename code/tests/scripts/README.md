# Ordner `code/tests/scripts/`

Eigenständige Diagnose- und Werkzeugskripte. Diese Dateien sind bewusst
**nicht** Teil der pytest-Ausführung (der Ordnername enthält kein `test_`
Muster und `pytest.ini` sammelt nur unter `tests/` Top-Level-Dateien).

> Vorher lagen solche Skripte als `tests/test_*.py` im pytest-Pfad –
> Modulcode auf Dateiebenen wurde dadurch bei **jedem** Testlauf
> ausgeführt (Netzwerk-Calls, Langsamkeit, Flaky-Failures). Bitte nicht
> rückbenennen.

## `htw_endpoint_diagnose.py`

Historisches Diagnose-Skript für den alten HTW-Server
(`f2ki-h100-1.f2.htw-berlin.de:11435`):

- `GET /api/tags` und `POST /api/chat` (native Ollama-Routen – lieferten zuletzt 404)
- `POST /v1/chat/completions` (LiteLLM/OpenAI-kompatible Route)
- gibt Status, Header und Antwortkörper jeder Anfrage aus

Die native HTW-Ollama-API wurde zum 01.09.2026 abgeschaltet; das Skript
hat daher nur noch dokumentarischen Wert (siehe AGENTS.md und
`docs/Infrastrukturprobleme.tex`).

## Bedenken

- Skripte enthalten ggf. fest kodierte URLs/Modelle und machen bei direktem Aufruf echte Netzwerkzugriffe.
- Keine API-Keys in Skripte einbetten – Keys gehören ausschließlich in `code/.env`.
