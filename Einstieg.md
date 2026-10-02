# Einstieg in die Evaluations-Testbench

Stand: 2026-10-02. Diese Anleitung fuehrt vom sicheren Offline-Demolauf zu
explizit freigegebenen Tutor- und Zweitmodellvergleichen. Das Notebook startet
keine echten Modellaufrufe, solange die jeweiligen Live-Gates ausgeschaltet sind.

## 1. Umgebung und Notebook starten

Python 3.11 ist die Referenzumgebung. Verwende fuer Installation und Notebook
dieselbe Python-Umgebung und waehle in Jupyter den dazugehoerigen Kernel.

Aus dem Repository-Stamm:

```bash
cd code
python -m pip install -r requirements.txt -r requirements-evaluation.txt
python -m jupyterlab evaluation/notebooks/testbench.ipynb
```

Alle weiteren Terminalbefehle dieser Anleitung werden aus `code/` ausgefuehrt,
sofern nicht anders angegeben. Jupyter darf das Notebook auch aus seinem eigenen
Verzeichnis starten; der Projektpfad wird automatisch erkannt.

Fuer den Offline-Einstieg werden weder Tutorserver noch Providerkey,
Evaluationtoken oder Datenbank benoetigt. Die Paketinstallation benoetigt
gegebenenfalls einen Netzwerkzugang, erzeugt aber keine LLM-Anfragen.

## 2. Sicheren Demolauf ausfuehren

Die Notebook-Konfiguration zunaechst unveraendert lassen:

```python
MODE = 'demo'
EXECUTE_LIVE = False
FETCH_SERVER_CONFIGURATION = False
EXECUTE_JUDGE_LIVE = False
CASE_SOURCE = 'tasks'
HINT_LEVELS = [0, 1]
```

Fuehre alle Zellen von oben nach unten aus. Das Notebook zeigt den Fallkatalog,
die Auswahlfelder, den Plan, Demoausgaben, Checks, Tabellen und Diagramme.

Der Standardplan umfasst vier ausgewaehlte Taskfaelle, drei Kontextprofile und
zwei Stufen, insgesamt **24 Jobs**. Der gesamte Taskkatalog enthaelt **15 Faelle**
zu zwei konkreten Funktionsinstanzen.

- Stufe 0 erzeugt eine diagnostische Einstiegsfrage.
- Stufe 1 gibt eine erste Orientierung.
- Demoantworten sind handgeschrieben und deutlich als solche markiert.
- Eine Antwort verraet absichtlich die Endloesung, um den Check vorzufuehren.
- Antwortzeiten, Modellentscheidungen und Ratings werden nicht erfunden.
- Die Demo geht nicht in empirische Modell- oder Humanratings ein.

Ein `server_start`-Plan bleibt im Demomodus `not_executed`: Eine individuelle
Modellentscheidung wird nicht simuliert und als echtes Ergebnis ausgegeben.

## 3. Aufgaben und Kontext bestimmen

Waehle im Notebook die Faelle, Profile und Stufen. Mit `custom` lassen sich die
zehn Kontextfelder einzeln ein- oder ausschalten. Danach die Planungszelle erneut
ausfuehren und Request sowie lokale Prompt-Vorschau kontrollieren.

| Auswahl | Bedeutung |
|---|---|
| `base` | Aufgabe und Studierendenantwort |
| `diagnosis_feedback` | Zusaetzlich vorgegebenes synthetisches Fehlerszenario und Feedback |
| `custom` | Frei bestimmte Kontextfelder; im Default zusaetzlich Lernziele |
| `LEVEL_MODE = 'direct'` | Explizite Startstufe aus `HINT_LEVELS` |
| `LEVEL_MODE = 'server_start'` | Server waehlt den festen oder individuellen Start; `HINT_LEVELS = [0]` ist nur ein Planplatzhalter |
| `USE_SERVER_CONTEXT = True` | Serverdefaults verwenden; Profilflags bestimmen weiterhin die verfuegbaren Daten |

Fuer einen gepaarten Profilvergleich `base` mit auswaehlen. Die aktuelle
Taskfallbank hat keine Scores oder `math_rules`; Bedingungen, die solche Daten
fordern, werden ausgeschlossen statt mit erfundenen Werten ausgefuehrt.

Stufe 0 besitzt eine separate Kontextobergrenze. Loesungsschritte und Endloesung
brauchen immer Kontextfreigabe **und** die Freigabe der aktiven Stufenpolicy.
Die lokale Vorschau ist kein Nachweis des entfernten Serverprompts; bei Live-
Ausgaben gelten die tatsaechlich zurueckgegebenen `prompt_messages`.

Jede geaenderte Auswahl, Regelbedingung oder Demo-/Live-Konfiguration braucht eine
neue `RUN_ID`. Vorhandene Snapshots und Hashes nicht passend editieren.

## 4. Isolierten Tutor fuer Livevergleiche konfigurieren

Die vollstaendige Vorlage ist [code/.env.example](code/.env.example), die
Parameterreferenz [code/config/README.md](code/config/README.md).
Konfiguriere die Evaluationsinstanz ueber ihre Umgebung oder eine lokale,
git-ignorierte `code/.env`. Bestehende Zugangsdaten nicht ueberschreiben.

Eine moegliche erste **Vergleichsbedingung**, nicht eine bereits empirisch
bestimmte optimale Policy:

```dotenv
DATABASE_PATH=data/tutor-evaluation.db
LLM_MODEL=qwen3.8-27b
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=400
TUTOR_RULES_ID=pilot-provided-fixed
TUTOR_START_MODE=fixed
TUTOR_START_LEVEL=0
TUTOR_DIAGNOSIS_MODE=provided
TUTOR_POLICY_MODE=tutor
TUTOR_RESPONSE_FORMAT=structured
TUTOR_ADAPTIVE_ENABLED=0
EVALUATION_API_ENABLED=1
EVALUATION_API_TOKEN=<lokal-erzeugter-token>
```

Den Tokenplatzhalter durch ein lokales Secret ersetzen. Der Providerzugang
(`LLM_API_MODE`, `LLM_BASE_URL`, gegebenenfalls `LLM_API_KEY`) muss ebenfalls
konfiguriert sein. Modellalias und Allowlist muessen zur Instanz passen.
Keys und Tokens niemals in Notebookzellen, URLs oder Laufartefakte eintragen.

Server in einem eigenen Terminal starten:

```bash
python -m uvicorn app.main:app --port 8000
```

Waehrend eines Vergleichslaufs keine Regeln aendern. Env-/Policyaenderungen
benoetigen einen Serverneustart und eine neue Lauf-/Bedingungsidentitaet.
Die eigene Datenbank trennt Evaluationschats von vorhandenen Tutor-Sessions.

Der Client, also die Jupyter-Umgebung, benoetigt fuer geschuetzten Configzugriff,
Simulation und Judge `TUTOR_EVALUATION_TOKEN` mit demselben Wert wie das
serverseitige `EVALUATION_API_TOKEN`. Er wird als `X-Evaluation-Token` gesendet,
nicht als Providerkey. Umgebungswerte vor dem Start von Jupyter bereitstellen;
keine echten Tokenwerte in versionierte Anleitungen oder Shellskripte aufnehmen.

## 5. Echte Tutorhinweise erzeugen

Im Notebook bewusst auf einen neuen Live-Lauf umstellen:

```python
MODE = 'live'
MODEL = 'qwen3.8-27b'  # expliziter, erlaubter Alias der Tutorinstanz
BASE_URL = 'http://127.0.0.1:8000'
RUN_ID = 'pilot-provided-fixed-001'
CONDITION_ID = 'pilot-provided-fixed'
LEVEL_MODE = 'direct'
HINT_LEVELS = [0, 1]
FETCH_SERVER_CONFIGURATION = True
EXECUTE_LIVE = False
EXECUTE_JUDGE_LIVE = False
```

Zunaechst Konfiguration, Auswahl und Plan pruefen. Der ausdruecklich freigegebene
Config-GET verwendet den Evaluationtoken, erzeugt aber keinen LLM-Aufruf.
Alternativ kann `EXPECTED_CONFIG_FILE` einen gespeicherten Public-Snapshot
offline laden.

Erst wenn die echten Aufrufe gewollt sind, `EXECUTE_LIVE = True` setzen und die
betroffenen Zellen ab der Konfiguration erneut ausfuehren. Die Generierungszelle
dispatcht dann den geplanten seriellen Lauf. Der Judge bleibt ausgeschaltet.

Das Standardbudget sind **80 gewichtete Einheiten/Stunde**: ein Generatorversuch
kostet konservativ 4, ein Judgeversuch 2. Ohne Judge sind dadurch hoechstens
20 Generatorrequests pro Stunde moeglich; ein 24-Job-Lauf kann am Budget warten.
Andere Runs und Clients desselben Providerkeys sind nicht mit abgedeckt.

## 6. Regeln, Startwahl und Adaption vergleichen

| Vergleich | Serverkonfiguration | Notebook |
|---|---|---|
| Vorgegebenes Fehlerbild vs. eigene Modellhypothese | `TUTOR_DIAGNOSIS_MODE=provided` vs. `model`; fuer getrennte Hypothesen in beiden Armen `structured` | Gleiche Faelle, sonstiger Kontext und Stufen; neue Run-/Condition-ID |
| Feste vs. individuelle Startwahl | `TUTOR_START_MODE=fixed` vs. `individual` | `LEVEL_MODE='server_start'`, `HINT_LEVELS=[0]` |
| Feste vs. adaptive Folgeunterstuetzung | `TUTOR_ADAPTIVE_ENABLED=0` vs. `1`, gleiche Startstrategie | Identisches explizites `INTERACTION_SCRIPT` |
| Tutor vs. allgemeiner Assistent | `TUTOR_POLICY_MODE=tutor` vs. `general` | Gleicher Modellalias, Taskkontext und Generierungsparameter |

Die Standard-Kontextobergrenze von Stufe 0 blendet Diagnose und Feedback auch
in `provided` aus. Fuer einen echten Fehlerkontrast entweder spaetere Stufen
verwenden oder die Stage-0-Freigabe ausdruecklich als Bedingung konfigurieren.
Die tatsaechliche Sichtbarkeit anhand der beobachteten Prompts kontrollieren.

Die gemeinsame Basisstufe wird anhand dokumentierter Pilotlaeufe **manuell**
ausgewaehlt und fuer weitere Vergleiche festgehalten. Sie ist weder automatisch
Stufe 1 noch das Profil `base`. Der Server speichert die anfaenglich gewaehlte
Sessionstufe separat von spaeteren Erhoehungen.

Beispiel eines ausdruecklichen Dialogskripts:

```python
INTERACTION_SCRIPT = [
    {'message': 'Ich verstehe nicht, wie ich anfangen soll.',
     'elapsed_seconds': 130, 'confusion_signal': True},
    {'message': 'Ich moechte erst selbst weiterdenken.',
     'elapsed_seconds': 130, 'confusion_signal': False},
]
```

Die Sekunden sind **simulierte Intervalle**, keine gemessene Lernzeit und kein
Sleep. Eine Erhoehung wird nur bei der naechsten Interaktion entschieden, wenn
Zeitgrenze und Verstaendnissignal zusammen vorliegen. Im Default ist sie aus.
Historie kann fuer `custom` mit einem Skript aktiviert werden; die aktuelle
Nachricht bleibt auch ohne Historie sichtbar.

Fertige Pilotplaene stehen unter [code/evaluation/experiments/](code/evaluation/experiments/):
`rule_comparison.json`, `start_comparison.json`, `adaptation_comparison.json`.
Sie konfigurieren nicht selbst den Server und starten keine Requests.

## 7. Ausgaben bewerten

Automatische Checks, Hinweisinspektion und Diagramme direkt im Notebook nutzen.
Ein fehlender Endloesungstreffer ist `inconclusive`, kein Abwesenheitsbeweis.
Stufe 0 wird als diagnostische Frage beurteilt, nicht als fehlender Rechenhinweis.

Menschenratings ueber das Notebookformular oder den neutralen CSV-Bogen
eingeben. Fuer blinde Reviews vorher keine Profil-/Modellansichten oder
`review_mapping.json` weitergeben. Leere Werte bleiben fehlend; negative
Bewertungen benoetigen eine Begruendung. Danach die Berichtszellen erneut
ausfuehren. Raster: [code/evaluation/rubric.md](code/evaluation/rubric.md).

Der optionale Zweitmodell-Judge braucht auf dem Server einen expliziten
`EVALUATION_JUDGE_MODEL` aus der Allowlist. Im Notebook `JUDGE_MODEL` auf einen
anderen Alias als den Generator setzen, eine neue `JUDGE_RUN_ID` waehlen und
erst bei gewollter Bewertung `EXECUTE_JUDGE_LIVE = True` aktivieren.
Vorbereitung und Bewertung verwenden gespeicherte erfolgreiche Liveausgaben.
Modellratings bleiben in eigenen Artefakten, getrennt von Menschenratings.
Ein anderer Alias belegt weder unabhaengige Gewichte noch verlaessliche Urteile.

## 8. Ergebnisse wieder ansehen und exportieren

```python
MODE = 'analyze'
RUN_ID = 'pilot-provided-fixed-001'
EXECUTE_LIVE = False
FETCH_SERVER_CONFIGURATION = False
EXECUTE_JUDGE_LIVE = False
```

Analyze laedt den bestehenden Lauf ohne neue Tutor-/Judge-Anfragen. Es kann
Checks und abgeleitete Dateien neu schreiben; passende Quellen-/Policyhashes
bleiben erforderlich. Originale Notebook-Eingabedateien sind dank der Snapshots
nicht notwendig.

Artefakte liegen unter `code/evaluation/runs/<RUN_ID>/`:

- `inputs/`: eingefrorene Aufgaben, Schema, Faelle, Profile und Konfiguration.
- `events.jsonl`, `generations.jsonl`, `checks.jsonl`: Versuche und Befunde.
- `reviews/`: neutrale Menschenreviews und getrennte `judge/<ID>/`-Ergebnisse.
- `derived/`: CSV-Tabellen, Diagramme und Markdownberichte.

Mit `COMPARE_RUN_DIRS` weitere gespeicherte Bedingungen auswaehlen. Der aktuelle
Lauf dient als Referenz. Effektive Start-/Hilfestufen bleiben Outcomes und
werden nicht als Voraussetzung fuer passende adaptive Vergleichspaare verwendet.

Bei Fortsetzung eines Live-Laufs `RESUME = True` bewusst setzen. Erfolgreiche
oder unklare Versuche werden nicht wiederholt. Fehlgeschlagene Folgefragen
werden ohne API-Idempotenz nicht erneut gesendet; sie blockieren abhaengige Turns.
Bei veraenderten Bedingungen oder Hashabweichungen eine neue Lauf-ID verwenden.

## Pruefung und Grenzen

Lokale Tests ohne externe LLM-Aufrufe:

```bash
python -m pytest -m "not integration" -v
```

Integrationstests nur gesondert und ausdruecklich freigeben. Vor einem Commit
Notebookoutputs und Execution Counts leeren; Secrets, Datenbanken und
personenbezogene Laufdaten nicht versionieren. Falls `RUN_ROOT` ausserhalb des
standardmaessig git-ignorierten Laufordners liegt, dessen Schutz separat pruefen.

Die Testfaelle sind authored Referenzhypothesen mit `pending`-Status. Reale
Modellausgaben darauf sind kontrollierte empirische Beobachtungen, keine
PRT-Verifizierung oder Nachweise fuer Motivation und Lernerfolg. Eine im
Dialogskript vorgegebene korrekte Antwort ist kein beobachteter Lerngewinn.

Weiterfuehrend: [Evaluationsbedienung](code/evaluation/README.md),
[Umgebungsparameter](code/config/README.md), [API-Vertraege](code/app/README.md),
[Forschungsprotokoll](docs/evaluation_protocol.md).
