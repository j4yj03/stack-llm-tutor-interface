# KI-Tutor für Moodle-STACK-Aufgaben

Stand: 2026-10-02. Selbst betreibbares FastAPI-Tutorinterface fuer digitale
Mathematikaufgaben in Moodle/STACK und kontrollierte empirische LLM-Vergleiche.
Inference nutzt standardmaessig GWDG SAIA, alternativ lokales Ollama.
STACK/Maxima bleiben bei tatsaechlicher Integration und vorliegender Evidenz die
autoritative mathematische Bewertungsquelle; der Tutorlink fuehrt kein Grading aus.

## Funktionen

- Generische Standardstufen 0 bis 4: Diagnosefrage, Orientierung,
  Strukturierung, konkreter naechster Schritt und ausfuehrliche Unterstuetzung.
  Texte, Wort-/Schrittlimits und Referenzfreigaben sind Vergleichsbedingungen,
  keine empirisch bewiesene optimale Progression.
- Explizite, feste oder individuelle Startwahl mit persistierter Baseline;
  optionaler Aufstieg erst bei neuer Interaktion aus Zeit plus Selbstbericht.
  Defaultstart ist fest auf 1, Adaption ist aus, kein Hintergrundtimer.
- Bereitgestellter Fehlerkontext oder eigenstaendige **unsichere** Modellhypothese,
  konfigurierbar mit `TUTOR_DIAGNOSIS_MODE=provided|model|none`; synthetische Labels
  sind keine PRT-Befunde. Default ist `provided`.
- Tutor- versus allgemeine Assistentenbedingung, zehn Kontextflags und
  Text-/JSON-Ausgabe ueber denselben Promptpfad.
- HTML-Chat ohne JavaScript, serverseitiger Verlauf, Retry ohne doppelte
  Nutzerfrage und Debuganzeige des tatsaechlichen Hinweis-Prompts.
- Strikte Task-JSON-/Policyvalidierung, SQLite-Sessions und additive Migration
  fuer initiale Baseline und Sessionzustand.
- Offlineplanung, Jupyter-Testbench, explizit freigegebene Live-API-Laeufe,
  Checks, neutrale Humanratings und separat freigegebener optionaler Judge v2.

## Architektur

```text
Moodle/STACK oder kontrollierter Task-/Antwortfall
    -> FastAPI: Validierung, Startwahl und effektiver Kontext
    -> zentrale HintPolicy + ein PromptBuilder-Pfad
    -> austauschbarer SAIA-/Ollama-Client
    -> Erfolgscommit: Hint, Stufe und Zustand in SQLite
    -> HTML oder JSON mit beobachteten Konfigurations-/Entscheidungsmetadaten

Evaluationsclient: Offlineplan/Snapshots -> autorisierte Tutor-API
    -> Checks und Humanratings -> separate optionale Judge-API/Modellratings
```

**Technologien:**
- Python, FastAPI/Uvicorn, Jinja2 und Pydantic 2.
- GWDG SAIA (OpenAI-kompatibel) oder nativer Ollama-Client.
- SQLite und JSON Schema Draft 2020-12 fuer lokale Aufgaben.
- Separate Evaluationsumgebung mit JupyterLab, Widgets, pandas, matplotlib,
  jsonschema und optionaler begrenzter SymPy-Pruefung.

## Voraussetzungen

- Python **3.11 als Referenzumgebung**. Die bereits gepinnte FastAPI-Version
  verlangt Python >=3.10; alte Python-3.9+-Angaben passen nicht zu diesen
  Abhaengigkeiten. Dies ist keine neue pauschale Plattform-/Versionsgarantie.
- Fuer Livegenerierung: eigener SAIA-Zugang ueber
  [SAIA-Dashboard](https://saia.gwdg.de/dashboard) oder explizit lokales Ollama.
  Offline-Demo/Planung brauchen keinen Provider. Beide Requirements-Dateien
  sind keine vollstaendigen Environment-Locks.

## Installation

Alle folgenden Pythonbefehle aus `code/` ausfuehren:

```bash
python -m pip install -r requirements.txt
```

Fuer Evaluation/Notebooks zusaetzlich:

```bash
python -m pip install -r requirements-evaluation.txt
```

Nach Updates an Server-, Formular- oder Taskcase-Abhaengigkeiten die jeweiligen
Requirements erneut installieren. Einrichtung allein startet keinen Livebatch.

## Umgebungskonfiguration

Konfiguration stammt beim Prozessstart aus Umgebungsvariablen oder der lokalen,
git-ignorierten `code/.env`. Vorlage ohne Secrets:
[code/.env.example](code/.env.example); vollstaendige Referenz mit Grenzen:
[code/config/README.md](code/config/README.md).

```env
LLM_API_MODE=saia
LLM_BASE_URL=https://chat-ai.academiccloud.de/v1
LLM_API_KEY=
LLM_MODEL=qwen3.8-27b
LLM_TIMEOUT=180
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=400
MAX_HINT_LEVEL=4
TUTOR_START_LEVEL=1
TUTOR_START_MODE=fixed
TUTOR_DIAGNOSIS_MODE=provided
TUTOR_POLICY_MODE=tutor
TUTOR_RESPONSE_FORMAT=text
TUTOR_ADAPTIVE_ENABLED=0
EVALUATION_API_ENABLED=0
DATABASE_PATH=data/tutor.db
MAX_HISTORY_MESSAGES=12
```

Wichtige Hinweise:

- Keys und Evaluationstokens niemals versionieren, in URLs/Prompts/Notebooks
  einsetzen oder protokollieren. Kein Lesen realer `.env`-Secrets fuer Dokumentation.
- `MAX_HINT_LEVEL` erlaubt `0..32`; alle aktiven Stufen muessen in der Policy
  vorliegen. Bei Maximum 0 explizit `TUTOR_START_LEVEL=0` statt Default 1 setzen.
- Policydatei `HINT_LEVELS_PATH`, volle/partielle `TUTOR_HINT_POLICY_JSON`-Overrides
  und `TUTOR_LEVEL_<N>_*` fuer Namen/Ziele/Listen/Limits/Freigaben sind validiert.
  Referenzschritte und -endloesung brauchen immer Kontextflag **und** Stufenfreigabe.
- `TUTOR_ASK_ACTIVATING_QUESTION`, `TUTOR_HIDE_HINT_LEVEL`,
  `TUTOR_ENFORCE_WORD_LIMIT`, Kontext-/Stage-0-Flags, Generation und Adaption
  sind ausdrueckliche experimentelle Bedingungen. Vollstaendige Parameter oben verlinkt.
- `LLM_DISABLE_THINKING=1` fordert Unterdrueckung an, garantiert aber keinen
  effektiven Providermodus. Ollama sendet `think=not LLM_DISABLE_THINKING` und
  bei JSONmodus `format="json"`. SAIA kann einmal ohne Thinking-Erweiterung
  wiederholen; Providerattemptzahl und Tokenusage bleiben unbekannt.
- Aktive App-Policy, `/health`, Generierung und geschuetzter Config-Snapshot
  verwenden denselben Policystand/hash; kein Datei-Hot-Reload. Aenderungen
  brauchen Neustart und neue Evaluationsbedingung/-Run-ID.

## Starten

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Lokaler Entwicklungseinstieg; breitere Bereitstellung braucht Authentifizierung,
Zugriffs-/Debugkontrolle und Datenhaltungskonzept. APIbeschreibung:
`http://127.0.0.1:8000/docs`.

## API-Endpunkte

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/health` | GET | Aufgabenanzahl, Defaultmodell, `config_sha256` und `rules_id`, ohne Provideraufruf |
| `/tasks` | GET | Liste aller verfügbaren Aufgaben |
| `/start` | GET | Tutor-Hauptseite (aus Moodle) |
| `/tutor/{chat_id}/message` | POST | HTML-Formular für Rückfragen, rendert die Tutor-Seite neu |
| `/tutor/{chat_id}/retry` | POST | Generierung auf Versuchsstufe, ohne Nutzerfrage nochmals zu speichern |
| `/api/tutor/start` | POST | Tutor-Session starten |
| `/api/tutor/{chat_id}/next-hint` | POST | Nächsten Hinweis anfordern |
| `/api/tutor/{chat_id}/message` | POST | Nachricht im Chat senden |
| `/api/tutor/{chat_id}/history` | GET | Chat-Verlauf abrufen |
| `/api/evaluation/config` | GET | Opt-in, authentifizierter Tutor-/Judge-Snapshot, ohne LLM |
| `/api/evaluation/judge` | POST | Opt-in, authentifizierter getrennter Modellreview |

Evaluation ist standardmaessig deaktiviert (404). Aktivierung braucht
`EVALUATION_API_ENABLED=1` und nichtleeren serverseitigen `EVALUATION_API_TOKEN`;
der Client liest `TUTOR_EVALUATION_TOKEN` und sendet `X-Evaluation-Token`
(bei fehlendem/falschem Token 401). Das ist kein Providerkey und kein Schutz
der normalen Tutor-/JSON-Debugrouten. Judge braucht einen expliziten erlaubten
`EVALUATION_JUDGE_MODEL`; das Werkzeug verlangt einen Alias verschieden von
allen gespeicherten Generatoraliasen, nicht einen Beweis unabhaengiger Gewichte.
Alle Payload-/Responsevertraege: [code/app/README.md](code/app/README.md).

## Testen

```bash
python -m pytest -m "not integration" -v
```

Integrationstests nur nach expliziter Freigabe; ungefiltertes `pytest` kann
echte Provideraufrufe ausfuehren. Offline-Testvertraege inklusive Stage 0,
Startwahl, Migration, Adaption, Config-/Judgeauth und Notebookrunde:
[code/tests/README.md](code/tests/README.md). Testdoubles belegen weder aktuelle
Moodle-/STACK-Abnahme noch mathematische Referenzverifizierung; keine globale
Testpasszahl wird hier behauptet.

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

Die Snippets senden unveraendert **explizit `hint_level=1`**. Das umgeht
serverseitige Defaultstartwahl; ein geaenderter Startdefault aktiviert dort
nicht automatisch Stage 0. Der Link ist editierbar und keine authentifizierte
PRT-Bewertung. Serverherkunft ist konservativ `provided`. Moodle-`debug:0`
unterdrueckt Diagnosemarker, Server-`DEBUG_MODE=0` blendet nur HTMLdebug aus.
Beide sind verschieden. Echte Deploymentvalidierung bleibt ausstehend.

## Tutor-Seite

Die Seite braucht kein JavaScript. Neue Chats nutzen explizite Stufe oder
`fixed|individual`; individuell zuerst begrenzte Auswahl `0..MAX_HINT_LEVEL`
aus Requestflags geschnitten mit Stage-0-Cap und Diagnosemodus, dann der Hint.
`baseline_hint_level` bleibt initial; bestehende Chats lehnen geaenderten
deklarierten Kontext und niedrigere Stufen ab, ohne damit STACK-Grading zu leisten.
Die additive DB-Migration ergaenzt `baseline_hint_level` und
`session_state_json`, ohne Chats/Nachrichten zu loeschen. Bei alten Zeilen gilt
deren aktuelle Stufe als Legacybaseline, nicht eine rekonstruierte historische
Startstufe; unbekannter Sessionzustand beginnt mit `{}`.

Defaultfragen bleiben auf derselben Stufe. Eingeschaltete Adaption braucht
erst beim naechsten POST Zeitgrenze **und** Selbstbericht (Defaults 120 Sekunden,
Schritt 1, Ceiling aktive Obergrenze). Intervalle nutzen nur monotone Uhr und
UUID desselben Prozesses; Neustart/Workerwechsel bedeutet unbekannte Zeit,
keine Wallclockinferenz oder aktive Lernzeitmessung. Explizite authentifizierte
Skriptintervalle sind requestweise Simulation, keine klebende Zeitquelle.
Fehler bewahrt die Nutzerfrage, commitet aber keinen Stufenaufstieg.

„Debug: erzeugter Prompt“ zeigt die Rollennachrichten **vor** der neuen Antwort,
auch bei einem fehlgeschlagenen LLM-Aufruf. Die JSON-Generierungsendpunkte liefern
dieselben Nachrichten im additiven Feld `prompt_messages`. Debug-Daten enthalten
Aufgabe und Chatverlauf: Vor produktiver Nutzung entfernen oder Zugriff beschränken.
Die Anzeige ist kein zusätzlich gespeichertes Prompt-Archiv.

JSONantworten liefern echte Hinweis-/Auswahlmessages, angeforderte/effektive
Flags, Baseline, Start-/Adaptionsentscheidung, Hypothese, aktive Policy und
Konfigurationshash. Die aktuelle Frage bleibt sichtbar, auch wenn Stage 0 die
Historie kappt. `DEBUG_MODE=0` unterdrueckt keine JSON-Debugfelder. Structured
speichert nur `hint`, gibt `diagnosis_hypothesis` separat aus; diese ist keine Note.

Der Retry ist UI-Hilfe, kein dauerhafter Fehlernachweis, Sessionlock oder
Idempotenzprotokoll. Mehrfaches POSTen kann weitere Antworten erzeugen.

## Forschungsprojekt

Die [Jupyter-Testbench](code/evaluation/notebooks/testbench.ipynb) bietet
Beispielaufgaben, frei waehlbare Kontextfelder, Tutor-API-Laeufe und die
Auswertung der Hinweise mit Checks, Bewertungsformularen und Diagrammen.
Sie startet standardmaessig als Offline-Demo ohne LLM-Aufrufe.
Installation und Forschungsgrenzen: [Evaluationssuite](code/evaluation/README.md).

Aktuelles Design: [eval-protocol-2](docs/evaluation_protocol.md). Default:
`CASE_SOURCE='tasks'`, vier Taskfehlerfaelle x drei Profile x Levels 0/1 x eine
Wiederholung = 24 Jobs. Zwei Tasks enthalten 15 authored Antworten zu zwei
expliziten festen Funktionen, passend zu deren Beispielreferenzen. Sie bleiben
`draft`, `synthetic_fixture`, Mathematik/Diagnose `pending`, Score/Seed `null`.
Der aeltere 12-Faelle-/4-Instanzen-Fixturekorpus ist separat.

| Feste Taskinstanz | Funktion | Antworten |
|---|---|---:|
| `task-chain-exp-f1` | `f(x)=-5*exp(x^2-2*exp(x))` | 9 |
| `task-prod-f1` | `f(x)=x^2*sin(x)` | 6 |

Die erste kontrollierte empirische Studie braucht keinen PRT: reale
Liveausgaben auf solchen Hypothesen sind empirisch, handgeschriebene Demos
sind es nicht. Erwartete Fehler/Referenzen sind keine verifizierten Urteile.
Die gemeinsame Pilotbaseline wird manuell anhand dokumentierter Pilotbelege
gewaehlt und eingefroren; weder Profil `base` noch Betriebsdefault 1 sind ein
automatisches Optimum. Lernwirksamkeit, Motivation und PRT-Genauigkeit sind
nicht durch die implementierten Checks/Scriptturns nachgewiesen.

Offlineexport und Planung:

```bash
python -m evaluation --help
python -m evaluation cases-from-tasks --tasks-dir tasks \
    --output evaluation/data/task_cases_local.jsonl
```

Ein neues, separat validiertes Protokoll-2-Experiment braucht fuer Taskfaelle
`allow_task_derived_cases=true` und `allow_unverified_cases=true`; bei CLIplanung
Korpus/Profiles ausdruecklich angeben. Alte `pilot.json`/`context_core.json`
behalten Protokoll 1. Gelieferte Protokoll-2-Piloten sind `rule_comparison.json`,
`start_comparison.json` und `adaptation_comparison.json`; Bedienung im
[Evaluations-README](code/evaluation/README.md). Die Plaene sind keine
abgeschlossene Studie. Planung dispatcht nichts, alte Hashes niemals passend editieren.

Livegenerator braucht gesonderte Freigabe und isolierte `DATABASE_PATH`, Judge
eine weitere Freigabe. Frischer Chat je Session, Skriptturns seriell nur nach
erfolgreichem Vorgaenger. Configdrift blockiert, fehlgeschlagene Folge-POSTs
werden ohne Idempotenz nicht replayed. Gemeinsames serielles Runbudget:
80 Einheiten/Stunde, Generator 4, Judge 2, daher ohne Judge 20 Generatorrequests/h
plus logische Obergrenze 35/h. Keine globale Quota fuer andere Runs/Keynutzer.

Judge v2 beurteilt getrennt Hypothese, aktuelle Nachricht, Turn und beobachtete
Regelsettings; fehlender Generatorprompt bleibt unbekannt. Human-/Judgeratings
bleiben in eigenen Artefakten/Reports mit Teilratings, fehlenden Werten und n/N.
Keine kompensierende Gesamtnote, keine erfundenen Token/Modelldigests oder
Providerattemptzaehler. CLI bietet derzeit keine Judge-Unterbefehle.

Weitere Einstiege: [Anwendungsuebersicht](code/README.md),
[Dokumentationsstatus](docs/README.md) und [Agentregeln](AGENTS.md).

## Grenzen

- Referenz-Doppelfreigabe ist Promptschutz, kein vollstaendiger semantischer
  Outputfilter. Kein Endformeltreffer ist kein Abwesenheitsbeweis.
- STACK-API-Grading und volle Moodle-/Maxima-Abnahme fehlen weiterhin;
  verifizierte externe Bewertung braucht spaeter echte passende Evidenz.
- UUIDs, HTTPS und institutionelle Inference ersetzen keine Autorisierung oder
  rechtliche Pruefung. Vor realen Studierendendaten Rechtsgrundlage, Empfaenger,
  Speicherung/Loeschung, Zugriff, Logs/Backups und Judgeverarbeitung klaeren.
  Moodle-GET-URLs koennen Antworten in Browser-/Proxylogs hinterlassen.
- SQLite, fehlende Sessionlocks/Idempotenz und prozessgebundene Uhr begrenzen
  Mehrworker-/Produktionsbetrieb. Standarddebug ist Entwicklung, keine Betriebssicherheit.

Dieses Projekt ist Teil einer Masterarbeit an der HTW Berlin:
*„Entwicklung eines KI-gestützten Tutors für Moodle-STACK-Aufgaben in mathematischen Grundlagenmodulen"*
