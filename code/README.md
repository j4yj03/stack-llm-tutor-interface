# Anwendungsordner `code/`

Stand: 2026-10-02. Prototyp fuer Moodle/STACK mit konfigurierbarer Tutorpolicy
und kontrollierten empirischen Vergleichen. Diese Beschreibung dokumentiert
die Implementierung, nicht die Konfiguration einer laufenden Installation.

## Struktur

```text
app/main.py             Tutor-Routen, Startwahl und Generierung
app/config.py           Zentrale Umgebungsparameter und Fail-fast-Validierung
app/runtime_config.py   Effektive Kontextflags, oeffentliche Konfiguration, SHA-256
app/adaptation.py       Reine Entscheidung bei der naechsten Interaktion
app/evaluation_api.py   Geschuetzte Konfigurations- und Judge-Routen
app/hint_policy.py      Generische Policydatei und validierte Overrides
app/prompt_builder.py   Ein gemeinsamer Promptpfad fuer alle Tutorbedingungen
app/schemas.py          Pydantic-Anfrage- und Antwortmodelle
app/database.py         SQLite-Initialisierung und additive Migration
app/chat_store.py       UUID-Sessions, Baseline, Zustand und Nachrichten
app/llm/                Austauschbare SAIA-/Ollama-Clients
app/templates/          HTML-Chat ohne JavaScript
config/                 Generische Hilfestufen 0..MAX_HINT_LEVEL
data/                   Lokale SQLite-Dateien, nicht versioniert
moodle/                 Feldbezogene STACK-JS-/CASText-Bausteine
schemas/                JSON-Schema fuer lokale Aufgaben
tasks/                  Generische Aufgaben und explizite Evaluationsbeispiele
evaluation/             Planung, Runner, Checks, Expertenratings und Zweitmodell
tests/                  Offline-Tests und explizit markierte Integrationstests
.env.example            Vollstaendige Vorlage ohne Zugangsdaten
```

## Setup

Alle folgenden Python-Befehle aus `code/` ausfuehren. Python 3.11 ist die
Referenzumgebung; die gepinnten Serverabhaengigkeiten sind keine Zusage fuer
Python 3.9 und weder Requirements-Datei ist ein vollstaendiger Environment-Lock.

```bash
python -m pip install -r requirements.txt
```

Lokale Einstellungen stammen aus der Umgebung oder `code/.env`; die Vorlage
ist [.env.example](.env.example). Providerkeys und Evaluationstokens niemals
versionieren, in URLs einsetzen oder in Laufartefakte schreiben.

## Starten

```bash
python -m uvicorn app.main:app --reload --port 8000
```

API-Dokumentation: `http://127.0.0.1:8000/docs`

## Tutorbedingungen

- Stufenbereich `0..MAX_HINT_LEVEL`, Maximum konfigurierbar `0..32`, Default `4`; Startbaseline
  `TUTOR_START_LEVEL=1`. Stufe 0 erzeugt im Tutormodus eine kurze Diagnosefrage.
- Ohne explizite Startstufe gilt `TUTOR_START_MODE=fixed|individual`.
  `individual` braucht vor dem Hinweis eine weitere LLM-Operation; eine
  explizite Stufe umgeht diese Auswahl. Die Moodle-Snippets senden keine
  Stufe und folgen damit der konfigurierten Serverstartwahl.
- `TUTOR_DIAGNOSIS_MODE=provided|model|none` trennt bereitgestelltes
  Fehlerszenario, unabhaengige unsichere Modellhypothese und keine Diagnose.
  Synthetischer Fehlerkontext ist kein PRT-Befund; verifizierte Ergebnisse
  bleiben verbindlich, sofern sie tatsaechlich bereitgestellt wurden.
- `TUTOR_POLICY_MODE=tutor|general` vergleicht didaktische Policy mit einem
  allgemeinen Assistenten. Kontext- und Stufenfreigaben fuer Referenzloesungen
  sowie Schutz vor eingebetteten Anweisungen bleiben in beiden Modi aktiv.
- Stufe 0 kappt angeforderte Kontextflags. Adaption ist standardmaessig aus;
  eingeschaltet wird sie erst bei einer Folgeinteraktion aus Zeitintervall
  plus Selbstbericht entschieden, nie durch einen Hintergrundtimer.
  Normale Intervalle gelten nur in derselben monotonen Prozessuhr; nach
  Neustart/Workerwechsel bleibt Zeit unbekannt, ohne Wallclockinferenz.
- Generierungsparameter, Regeltexte, Startwahl, Kontext und Adaption sind
  explizite Bedingungen. Vollstaendige Umgebungsreferenz und Policy-Migration:
  [config/README.md](config/README.md). API-Vertraege: [app/README.md](app/README.md).

## Tests

```bash
python -m pytest -m "not integration" -v
```

Integrationstests nur mit gesonderter Freigabe ausfuehren; vorhandene Keys
koennen echte Provideraufrufe ermoeglichen. Details: [tests/README.md](tests/README.md).

## Evaluation (fachliche Test-Suite)

Die Suite plant offline. Echte Ausgaben benoetigen `--execute-live` bzw. eine
ausdrueckliche Notebookfreigabe und eine isolierte Tutor-Datenbank. Vergleiche
von Deploymentbedingungen pinnen `condition_id`, erwarteten/beobachteten
Serverhash, Policy, Input- und Skripthashes. Direkte Zielstufen und serverseitige
Startwahl sind verschiedene Experimente; Skriptzeiten sind Simulation,
keine gemessene Lernzeit.

Interaktiver Einstieg mit Beispielaufgaben und konfigurierbarem Kontext:

```bash
python -m pip install -r requirements-evaluation.txt
python -m jupyterlab evaluation/notebooks/testbench.ipynb
```

Das Notebook startet als Offline-Demo mit Taskbeispielen und Levels 0/1.
Die Konfigurationszellen bieten Bedingung, Startwahl, Skript, Config-Snapshot
und separate Generator-/Judge-Gates. Das ist keine Aussage ueber aktuelle
Testpasszahlen. Der aktuelle Notebook-/CLI-/Python-Vertrag steht in
[evaluation/README.md](evaluation/README.md), das Bewertungsraster in
[evaluation/rubric.md](evaluation/rubric.md). Forschungsdesign:
[Evaluationsprotokoll](../docs/evaluation_protocol.md).
Notebookprotokoll: `eval-protocol-2`. Eine gemeinsame empirische Pilotbaseline
wird manuell ausgewaehlt und eingefroren, nicht automatisch empfohlen oder
aus dem Betriebsdefault 1 abgeleitet.

Die Aufgaben enthalten 15 explizite, task-abgeleitete synthetische Faelle.
Sie bleiben `draft/pending`, ohne STACK-Score oder Seed. Live-Ergebnisse auf
ihnen sind empirische kontrollierte Hypothesen, keine Verifizierung der PRTs
oder Nachweise fuer Lernwirksamkeit. Handgeschriebene Offline-Demos tragen
keine Forschungskennzahlen bei.

Optionale Zweitmodellratings laufen ueber `POST /api/evaluation/judge`, nie
direkt vom Client zum Provider. Server: `EVALUATION_API_ENABLED=0` als Default,
lokaler `EVALUATION_API_TOKEN`, expliziter `EVALUATION_JUDGE_MODEL`. Client:
`TUTOR_EVALUATION_TOKEN` als `X-Evaluation-Token`. Judgealias und Generatoralias
muessen fuer die Zweitmodellstudie verschieden sein. Experten- und
Modellratings bleiben getrennt; es gibt keine kompensierende Gesamtnote.
Judge v2 (`judge-rubric-1.0-v2`) beruecksichtigt getrennte Hypothesen,
Folgemessages, aktive Regelsettings und Berichte pro Turn.

## Wichtige Regeln

- Ungueltige Aufgaben, Policies und Konfigurationswerte verhindern den Start.
- Chat-UUIDs sind keine Authentifizierung. Die geschuetzte Evaluation ersetzt
  keine Zugriffssteuerung der normalen Tutor-/Debug-Routen.
- Der lokale Budgetzaehler umfasst serielle Generator-/Judge-Journale eines
  Laufs, nicht alle Clients desselben Providerkeys.
- Fehlende Evidenz, Teilratings, Fehlversuche und unbekannte Telemetrie bleiben
  sichtbar. Hashabweichungen brauchen passende Quellen oder neue Lauf-IDs,
  niemals nachtraeglich angepasste alte Hashes.
