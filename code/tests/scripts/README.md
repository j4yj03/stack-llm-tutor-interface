# Ordner `code/tests/scripts/`

Stand: 2026-10-02. Historische Diagnosewerkzeuge, keine aktuelle Tutor- oder
Evaluationsschnittstelle. Aktuelle Offlineverifikation:
[../README.md](../README.md); Bedingungs-/Judgepfad:
[../../evaluation/README.md](../../evaluation/README.md).

Eigenständige Diagnose- und Werkzeugskripte. Diese Dateien sind bewusst
**nicht** Teil der pytest-Ausfuehrung: ihre Dateinamen passen nicht zum
`test_*.py`-/`*_test.py`-Sammelmuster. `testpaths=tests` allein verhindert
keine rekursive Sammlung; daher weder umbenennen noch aus Testmodulen importieren.

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
[historische Infrastrukturprobleme](../../../docs/Infrastrukturprobleme.tex)).

Der Modulcode sendet Requests bereits bei Import. Weder `python`-Import noch
direkter Skriptaufruf ist ein Offlinecheck oder wird durch den neuen
Runner-/Judge-Live-Gate geschuetzt. Alte Requests/Modellnamen unveraendert als
historische Belege lassen; zum Aktualisieren keine Providercalls starten.

## Bedenken

- Skripte enthalten ggf. fest kodierte URLs/Modelle und machen bei direktem Aufruf echte Netzwerkzugriffe.
- Keine API-Keys in Skripte einbetten – Keys gehören ausschließlich in `code/.env`.
- Keine Evaluationstokens zu diesen Requests hinzufuegen. Aktueller Zugriff
  verwendet serverseitig `EVALUATION_API_TOKEN`, clientseitig
  `TUTOR_EVALUATION_TOKEN` im Header `X-Evaluation-Token`, nicht alte URLs.
- Stage 0, individuelle Startwahl, synthetische Diagnosehypothesen, neue
  Bedingungshashes und gewichtetes Generator-/Judgebudget sind hier nicht
  implementiert. Den vorhandenen Evaluationsrunner nutzen, nicht einen zweiten
  unprotokollierten Prompt-/Generierungsweg auf Basis dieser Skripte schaffen.
- Ausgabe kann Upstreamheader und Koerper enthalten. Historische Dumps vor
  Weitergabe auf sensible Daten pruefen; keine solchen Ausgaben als
  reproduzierbare Research-Telemetrie oder neu verifizierte Evidenz darstellen.
