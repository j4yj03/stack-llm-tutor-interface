# Ordner `code/evaluation/`

Stand: 2026-10-02. Korpus- und bedingungsbasierte Tutor-API-Experimente:
technische Checks, Referenzkonsistenz, didaktische Expertenratings und optionale
Zweitmodellratings bleiben getrennt. Konzept:
[Evaluationsprotokoll](../../docs/evaluation_protocol.md); aktuelle Serververtraege:
[../app/README.md](../app/README.md); vollstaendige Umgebungsreferenz:
[../config/README.md](../config/README.md); Kriterien: [rubric.md](rubric.md).

## Grundregeln

1. Kein Import von `app.main`, kein direkter Providerclient und keine lokale
   Tutor-Datenbankinitialisierung. Generierung nutzt Tutor-Routen, der Judge
   `/api/evaluation/judge`. Live-Aufrufe speichern auf dem Server Chats: eine
   isolierte Datenbank verwenden. Die lokale Vorschau ist kein Serverprompt.
2. **Kein Netz ohne Freigabe**: `validate` und `plan` sind offline.
   `run --execute-live` bzw. `execute_judge_run(execute_live=True)` verlangen
   eigene Freigabe; vorhandene Keys/Tokens starten nichts von selbst. Ein
   zusaetzlicher Notebook-Config-GET braucht seinen eigenen expliziten Fetch-Gate.
3. Frischer Chat je Session (`Fall x Profil x Startbedingung x Modell x
   Wiederholung`). Ohne Skript ist ein Job eine einzelne Antwort. Explizite
   Skriptturns benutzen denselben Chat und haengen von erfolgreicher
   Vorgaengerantwort ab; Turns sind keine unabhaengigen Faelle.
4. Alle zehn Kontextflags sind in Profilen explizit. Im Default werden sie
   gesendet; `use_server_context=true` untersucht stattdessen beobachtete
   Serverdefaults. Profilflags bestimmen weiterhin die verfuegbaren Falldaten.
5. **Korpus trennt Input und Bewertung**: `tutor_context` (potentielle
    Request-Felder) vs. `evaluation_only` (Referenzen, Prüfstatus,
    Provenienz). Referenzschritte/-endloesung werden nur fuer die
    entsprechenden Profile in den Request uebernommen; beim Schritteprofil
    dient die Endloesung zudem als interner Guard-Wert. Bewertungsstatus,
    Aequivalentformen und Verifizierungs-/Bewertungsmetadaten gehen niemals
    an den Generator. `diagnosis_source` beschreibt separat die Herkunft eines
    bereitgestellten Fehlerszenarios, ohne PRT-Evidenz zu behaupten.
6. **Keine stillen Retries, kein stiller Modellwechsel**, unklare
   Transportversuche bleiben unklar; Resume wiederholt nichts automatisch.
7. **Telemetrie ehrlich**: nicht beobachtbare Werte (Token, Upstream-Versuche)
   bleiben `unbekannt`, werden nie geschätzt.
8. Eine Bedingung ist ein konfiguriertes Deployment, keine vom Client
   eingeschmuggelte Tutorregel. Hashabweichungen blockieren weitere Requests;
   alte Snapshots/Hashes niemals editieren, um Resume zu erzwingen.
9. Synthetische Referenzen und erwartete Fehler sind gemeinsame kontrollierte
   Hypothesen, keine objektiven PRT-Urteile. Liveausgaben sind empirisch;
   Offline-Demos/Mocks tragen weder Human- noch Judge-Forschungskennzahlen bei.

## Bestandteile

| Datei/Ordner | Verantwortung |
|---|---|
| `models.py` | Strenge Datenmodelle (unbekannte Felder → Fehler) |
| `corpus.py` | Fall-/Profil-/Experiment laden, Eignung, Request-Payload |
| `runner.py` | Deterministischer Session-/Turnplan, Bedingungsidentitaet, Serverpreflight, gewichtetes Budget, Journal und Resume |
| `notebook.py` | Auswahl-Snapshots, lokale Prompt-Vorschau, explizit markierte Offline-Demo |
| `checks.py` | Automatische Prüfungen + begrenzte symbolische Formelprüfung |
| `report.py` | Human-Review-Export/-Import, bedingungs-/phasen-/turnbewusste Reports und `compare_runs` |
| `task_cases.py` | Offlineableitung authored Taskbeispiele; niemals STACK-/PRT-Verifizierung |
| `judge.py` | Offline-Judgeplanung, eigener Live-Gate, getrennte Modellratings und optionale Human-Abweichungsvergleiche |
| `__main__.py` | CLI: cases-from-tasks/validate/plan/run/check/review-export/review-import/report |
| `rubric.md` | Bewertungsraster (rubric-1.0) mit Skalenankern |
| `data/` | Profile und aelterer Fixture-Korpus; optional spaeter `cases_research.jsonl` fuer verifizierte externe Bewertung |
| `experiments/` | Protocol-2-Piloten `rule_comparison.json`, `start_comparison.json`, `adaptation_comparison.json`; historische Protocol-1-Presets bleiben unveraendert |
| `notebooks/testbench.ipynb` | **Interaktive Testbench**: Fall-/Profil-/Stufenwahl, Kontext-Checkboxen, Request-/Prompt-Vorschau, Demo/Live/Analyse, Checks, Ratings im Notebook, Tabellen/Diagramme und Export |
| `notebooks/auswertung.ipynb` | Historischer Offline-Artefaktleser; alte Aggregationen nicht als aktuellen Bedingungsreport behandeln |
| `imports/` | Rohdaten der späteren STACK-/Moodle-Exporte (git-ignoriert) |
| `runs/` | Laufartefakte (git-ignoriert) |

Der aktuelle empirische Hauptpfad (`eval-protocol-2`) untersucht kontrollierte
Task-/Fehlerhypothesen ohne PRT-Voraussetzung. Ein spaeterer evidenzbasierter
STACK-/PRT-Vergleich ist ein eigener Untersuchungsabschnitt; das alte
`context_core`-Preset definiert nicht die Voraussetzungen aller Forschung.
Diese Studienabschnitte sind keine Tutor-Hilfestufen oder API-Phasen.

## Kontextprofile

| Profil | extras gegenüber base | Zweck |
|---|---|---|
| `base` | — | Aufgabe + Antwort |
| `diagnosis` | Diagnosecode | strukturierte Diagnose |
| `feedback` | bereitgestellter Feedbacktext | Feedback ohne Code, Herkunft bleibt separat |
| `diagnosis_feedback` | Code + Feedback | inkrementeller Feedback-Effekt |
| `knowledge` | + Lernziele + Regeln | Fachkontext |
| `steps` | + Referenzschritte | Standardvergleich auf Stufe 3; Verifizierung nicht automatisch gegeben |
| `solution` | + Referenzendloesung | Standardvergleich auf Stufe 4, getrennt von frueher Unterstuetzung |

`include_score` und `include_chat_history` sind in den festen Profilen `false`.
Explorative Profile duerfen nur verfuegbare Falldaten anfordern: Score `null`
ist fehlend, `0.0` ist ein echter Wert. Schritte brauchen auch die passende
Referenzendloesung als internen Literalguard, selbst wenn das Finalflag aus ist.
Fehlende benoetigte Daten schliessen eine Zelle aus, statt den Kontext still
zu verkleinern. Ein Historienprofil verlangt ein explizites Interaktionsskript;
bei einem frischen Einzelturn wird es durch die Experimentvalidierung abgewiesen.

Die effektiven Flags koennen von angeforderten Flags abweichen: Stage 0 kappt
nach konfigurierter Obergrenze, `model|none` blendet Diagnose/Feedback aus.
Vergleiche diese dokumentierten Filter mit den zurueckgegebenen Flags, nicht
mit einem angenommenen Default. Score wird durch die Diagnosemodi nicht entfernt.
Wichtig: `include_final_answer=false` bedeutet „Referenzendlösung nicht im
Prompt“ — die **Ausgabe**-Erlaubnis richtet sich nach der aktiven Stufenpolicy.
Bei Defaultstufe 4 ist eine Endloesung auch ohne Promptreferenz nicht automatisch
ein Regelverstoss. Der Bericht fuehrt
`complete_solution_present` und `prohibited_disclosure` deshalb getrennt.
Bei angepassten Policies ist die tatsaechliche Freigabe massgeblich, nicht
pauschal die Zahl 4. Im General-Modus ist die didaktische Outputpolicy inaktiv;
die Prompt-Doppelfreigabe fuer Referenzen bleibt trotzdem verpflichtend.

## Deploymentbedingungen

`Experiment` modelliert eine kontrollierte Bedingung, nicht einen globalen
Mix von Deploymentparametern innerhalb eines Laufs:

| Feld | Default | Bedeutung |
|---|---|---|
| `condition_id` | `default` | Eindeutiges Label fuer die untersuchte Deploymentbedingung |
| `expected_config_sha256` | `null` | Optional vorab gepinnter SHA-256 der geheimnisfreien Serverkonfiguration |
| `level_mode` | `direct` | Direkte Zielstufe oder `server_start` |
| `use_server_context` | `false` | Kontextflags im Request senden oder Serverdefaults beobachten |
| `interaction_script` | `[]` | Explizite geordnete Folgefragen, simulierte Intervalle/Signale und optionale Zielstufen |
| `request_budget_units_per_hour` | `80` | Gewichtetes gemeinsames Budget fuer dieses serielle Runjournal |
| `max_generations_per_hour` | `35` | Zusaetzliche Obergrenze logischer Generatorrequests |
| `allow_unverified_cases` | `false` | Bewusste kontrollierte Hypothesen statt unbelegt als verifiziert auszugeben |
| `allow_task_derived_cases` | `false` | Separater Opt-in fuer aus Taskbeispielen abgeleitete synthetische Faelle |

`level_mode="direct"` sendet explizite `hint_levels`, einschliesslich 0.
Das Evaluationsmodell erlaubt `0..32`; die beobachtete Serverpolicy kann den
Bereich weiter einschraenken. `server_start` verlangt `hint_levels=[0]`
(auch Kontrollen mit Level 0), sendet aber `hint_level=null`. Die 0 im Plan
ist dann **nur Platzhalter**, keine Behauptung ueber die gewaehlte Stufe.
Effektive Stufe, Baseline und Phase sind beobachtete Outcomes.

Serverdefaults: Startlevel 1, Modus `fixed`; `individual` fuehrt vorher eine
weitere LLM-Auswahl durch. Fuer den Vergleich feste versus individuelle
Startwahl `server_start` benutzen, sonst umgeht eine explizite Stufe die
Startbedingung. Auswahl- und Antwortprompts separat sichern. Stufe 0 beurteilt
eine diagnostische Frage, nicht einen rechnerischen naechsten Schritt.
Die gemeinsame Pilotbaseline wird nach einer dokumentierten Auswahlregel
manuell festgelegt und eingefroren; keine automatische Optimalauswahl durch
die Suite. Betriebsdefault 1, persistierte Chatbaseline und Profil `base` sind
davon verschiedene Begriffe. Individuelle Auswahl nutzt die Requestflags
geschnitten mit Stage-0-Cap, nicht einen unabhaengigen HTML-Defaultkontext.

Eine Bedingung kann beispielsweise diese Felder eines vollstaendigen
Experiments setzen; ein neuer Run muss die gesamten Inputs einfrieren:

```json
{
  "condition_id": "model-analysis-adaptive",
  "expected_config_sha256": null,
  "level_mode": "server_start",
  "hint_levels": [0],
  "use_server_context": true,
  "interaction_script": [
    {"message": "Ich verstehe nicht.", "elapsed_seconds": 130,
     "confusion_signal": true}
  ],
  "request_budget_units_per_hour": 80,
  "allow_unverified_cases": true,
  "allow_task_derived_cases": true
}
```

`null` bindet erst beim initialen autorisierten Preflight die beobachtete
Identitaet; es ist kein vorab verifizierter Bedingungsnachweis. Fuer geplante
Vergleiche einen echten `expected_config_sha256` aus einem autorisierten
Config-Snapshot setzen. `create_run(expected_config=...)` kann einen bereits
gespeicherten Snapshot offline pruefen/einbetten; der CLI-Plan nutzt den
Hash aus der Experimentdatei und liest die Korpusdatei aus `--cases`.

Jede initiale Liveausfuehrung und jedes Resume beobachtet `/health`. Fuer
Hashpin, Serverstart, Serverkontext, Skript oder vorhandenen Evaluationtoken
wird auch `GET /api/evaluation/config` gelesen. Health-/Confighash, vorheriger
Runtime-Snapshot und Responseidentitaet muessen uebereinstimmen. Manifest,
Plan, Bedingungen, Skript, Corpus/Profile, lokale Policy und Quellen werden
separat gehasht. Die lokale Policydatei ist keine Behauptung ueber das Deployment;
aktive Policy aus Response/Serverconfiguration hat bei modernen Checks Vorrang.
Die Hauptanwendung haelt diesen Stand in `app.state.hint_policy`: Config-GET
und Health nutzen dieselbe aktive Policy ohne Datei-Hot-Reload. Geaenderte
Umgebungs-/Policywerte brauchen Prozessneustart und eine neue Laufidentitaet.

Tutor-`config_sha256` identifiziert `tutor-config-1`, nicht die Judgeparameter.
Der geschuetzte Snapshot fuehrt Judge-Regel-ID/Alias/Parameter daneben;
Judgevorbereitung und Runtime-Snapshot pinnen diese zweite Identitaet separat.
`TUTOR_RULES_ID` ist nur ein Label; eine andere Regel bei gleichem Label wird
durch die effektiven Policy-/Konfigurationshashes sichtbar.

Die normalen Generierungsantworten liefern `configuration`, `config_sha256`,
`hint_policy`, `policy_mode`, `stage`, `baseline_hint_level`, `start_decision`,
`adaptation`, `diagnosis_hypothesis`, `prompt_messages`,
`start_prompt_messages` und `llm_operations`. Diese Operationenzahl ist nicht
der Providerattemptzaehler; Token und effektiver Thinking-Modus bleiben unbekannt.

`build_request_payload` normalisiert im gemeinsamen Korpuspfad
`synthetic_fixture` zu API-`diagnosis_source="synthetic"`, auch fuer CLI- und
Taskexportfaelle. Ohne bekannte Herkunft gilt `unknown`, ohne uebermittelten
Diagnose-/Feedbackkontext `null`; explizite gueltige Herkunft bleibt erhalten.
Korpusprovenienz und API-Herkunft sind getrennte Labels. Die Normalisierung
behebt deren Payloadkompatibilitaet, verifiziert aber keine pending-Referenz.

## Skript und Budget

Ein `InteractionTurn` enthaelt `message`, nichtnegatives endliches
`elapsed_seconds`, optional `confusion_signal` und `hint_level`. Der Runner
sendet Folgefragen seriell als `/api/tutor/{chat_id}/message` und das Intervall
als `simulation_elapsed_seconds`. Keine echte Lernzeit, kein kuenstlicher
Sleep. Der Server verlangt Evaluationauthentifizierung fuer Simulation/Signal;
seine JSON-Grenze fuer simulierte Intervalle ist `0..86400` Sekunden.

Zeit plus Selbstbericht wird erst bei der naechsten Interaktion ausgewertet;
Defaultadaption ist aus, Defaultschwelle 120 Sekunden, Schritt 1, Ceiling
`MAX_HINT_LEVEL`. Ein direkt angefordertes Level geht vor. Bei deaktivierter
Historie bleibt die aktuelle Nachricht sichtbar, alte Turns sind jedoch nicht
implizit Promptkontext. Beobachtete und simulierte Quellen getrennt auswerten.
Das gilt auch fuer durch Stage 0 gekappte Historie. Normale Intervalle sind
nur innerhalb derselben monotonen Prozessuhr/UUID verfuegbar; nach Neustart
oder Workerwechsel bleibt Zeit `null` (`time_unknown` bei aktivem
Verwirrungssignal), ohne Wallclockinferenz oder aktives Bearbeitungszeittracking.
Ein Simulationswert samt Zeitquelle gilt nur fuer seinen authentifizierten
Request, nicht automatisch fuer nachfolgende normale Turns.

Turn 0 startet frisch. Jeder Folgeturn braucht erfolgreichen Vorgaenger mit
passender Chat-/Modellidentitaet. Ein Fehler blockiert abhaengige Turns.
`--retry-failed` wiederholt nur bekannte Startfehler; fehlgeschlagene Folge-POSTs
werden auch dann nicht replayed, da Nutzerfrage oder Zustand bereits gespeichert
sein kann. Ambiguitaet oder ungueltige Responseidentitaet blockiert ebenfalls.
Keine automatischen Runnerretries, kein Modellfallback, keine erfolgreichen
Responses erneut senden.

Jeder Generatorrequest kostet konservativ **4 Budgeteinheiten**, jeder Judge
**2**. Die 4 decken auch individuelle Startwahl plus Hint und je einen
moeglichen SAIA-Fallback ab; sie sind keine gemessenen Providerattempts.
Default **80 Einheiten/Stunde**, daher maximal 20 Generatorrequests ohne Judge,
zusaetzlich zur Obergrenze 35 logischer Generierungen. Fehler, offene und
ambigue dispatchte Attempts verbrauchen Budget. Health-/Config-GETs erzeugen
keine LLM-Ausgabe. Resume rekonstruiert Kosten aus Generator- und allen
zugeordneten Judgejournals dieses Laufs; keine parallelen Livebatches als Default.

Das Budget ist keine globale Quota oder Sperre: andere Runs, Clients und
Providerkeynutzer fehlen. SAIA hat ungefaehr 100 Calls/Stunde; freie Quota
nicht annehmen. `http_timeout` (CLI-Default 420 Sekunden) explizit fuer
mehrere serielle Serveroperationen/Fallbacks planen; ein Timeout bleibt
ambiguous, keine implizite Retryfreigabe.

## Nutzung

Arbeitsverzeichnis `code/`; eine isolierte Tutor-Instanz mit eigener
`DATABASE_PATH` nutzen (nicht die produktive DB).

### Notebook

Python 3.11 wird fuer die separate Evaluationsumgebung empfohlen:

```bash
python -m pip install -r requirements-evaluation.txt
python -m jupyterlab evaluation/notebooks/testbench.ipynb
```

1. Mit `MODE = 'demo'` alle Zellen ausfuehren: keine Netzwerkaufrufe,
   keine LLMs und keine Datenbank. Die handgeschriebenen Demoausgaben
   zeigen die Checks einschliesslich einer absichtlich offengelegten Loesung.
2. Faelle, Profile und Stufen auswaehlen; fuer `custom` die Kontextfelder
   per Checkbox festlegen. Standard: vier Taskfaelle, drei Profile, Stufen 0/1,
   eine Wiederholung = 24 Jobs. Fuer einen Vergleich `base` beibehalten.
3. Planungszelle ausfuehren und Request/Prompt-Vorschau kontrollieren.
   Korpus, Profile und Experiment werden unter `runs/<RUN_ID>/inputs/`
   eingefroren. Geaenderte Konfiguration erfordert einen neuen `RUN_ID`.
4. Fuer echte Tutorhinweise: `MODE = 'live'`, explizites `MODEL` aus der
    Server-Allowlist, neue `RUN_ID`, `BASE_URL` der isolierten Instanz und
    `EXECUTE_LIVE = True`. Providerkeys bleiben auf dem Server;
    geschuetzte Funktionen nutzen separat den lokalen Clienttoken.
5. Automatische Checks und Tabellen auswerten; Hinweise fallweise unter
   verschiedenen Profilen vergleichen. Fachliche Ratings im Notebookformular
   speichern oder den neutralen CSV-Bogen extern bewerten und importieren.
6. Berichtszellen nach der Bewertung erneut ausfuehren. CSVs, Diagramme,
   Referenzdaten und Rohprompts liegen nur im git-ignorierten Laufordner.
   `MODE = 'analyze'` mit derselben `RUN_ID` laedt einen bestehenden Lauf
   ohne neue API-Aufrufe.

Der Beispielkorpus enthaelt **12 synthetische Faelle / 4 Aufgabeninstanzen**:

| Funktion | Falltypen | Anzahl |
|---|---|---:|
| `-5*exp(x^2-2*exp(x))` | innere Ableitung fehlt/falsch, Faktor fehlt, korrekte Aequivalentform, Prompt-Injection | 5 |
| `x^2*sin(x)` | Produktregel-Summand fehlt, Potenzableitung falsch, korrekte Antwort | 3 |
| `3*exp(2*x+1)` | innere Ableitung fehlt, konstanter Faktor fehlt | 2 |
| `x^3*exp(x)` | Produktregel-Summand fehlt, Potenzableitung falsch | 2 |

Alle bleiben `draft`, `synthetic_fixture`, `pending`: symbolische lokale
Plausibilitaetstests sind keine STACK-/PRT-Verifizierung. Kontrollierte
empirische Livevergleiche sind mit expliziten Opt-ins ohne PRT-Pruefung moeglich.
Nur eine spaetere Studie mit Anspruch auf verifizierte externe Bewertung
braucht belegte instanzbezogene Faelle und `ALLOW_UNVERIFIED_CASES=False`.
Fehlende Falldaten fuehren zu Ausschluessen, nicht zu stillen Kontextaenderungen. Fuer separate
Schritte-/Loesungsuntersuchungen `steps` auf Stufe 3 bzw. `solution` auf
Stufe 4 auswaehlen; bei der Defaultpolicy bleiben niedrigere Stufen trotz
gesetzter Checkbox gesperrt. Angepasste Policyfreigaben separat kontrollieren.

Ratingboegen sind ohne Modell-/Profilspalten. Fuer eine wirklich blinde
Expertenbewertung nicht vorab die Profilansichten zeigen und
`review_mapping.json` nicht weitergeben. Leere Felder bleiben fehlend;
ein erneuter Export erhaelt bereits ausgefuellte Bewertungsfelder.
Der Import akzeptiert UTF-8-CSVs mit und ohne BOM, Pflichtspalten werden
geprueft. Fuer Schritteprofile ist die Referenzendlösung als Guard Pflicht,
fuer aktivierten Score ein belegter Wert (auch `0.0` ist gueltig).
Fachliche Fehler, Stufeneinhaltung und Sprachqualitaet werden getrennt
berichtet. Keine Endloesung erkannt bedeutet `inconclusive`, nie ein
Abwesenheitsbeweis. Demoantworten und ihre Checks/Ratings sind aus
Forschungskennzahlen ausgeschlossen.

Das Notebook findet `code/` auch von seinem Unterverzeichnis aus.
Optional: `TUTOR_EVALUATION_RUNS` fuer einen anderen Artefaktordner und
`TUTOR_BASE_URL` fuer eine andere Tutorinstanz. Nach Kernelneustart kann
`RESUME = True` offene Jobs fortsetzen; das Stundenbudget wird fuer diesen
Lauf aus dem Journal rekonstruiert. Nutzung anderer Laeufe/Clients wird
nicht vom lokalen Runnerbudget erfasst.

Die aktuellen Notebookkonfigurationszellen enthalten folgenden Vertrag;
Implementierungsabgleich ist keine Behauptung erfolgreicher Run-All- oder
Deploymenttests. Auswahlwidgets steuern Faelle/Profile/Stufen, weitere
Bedingungen sind explizite Konfigurationswerte:

| Notebookwert | Default | Verhalten |
|---|---|---|
| `CASE_SOURCE` | `tasks` | Authored Taskbeispiele; `jsonl` behaelt den separaten Korpusweg |
| `TASKS_DIR`, `TASK_SCHEMA_PATH` | lokale Task-/Schemapfade | Ausgewaehlte Quellen und Schema werden mit eingefroren |
| `HINT_LEVELS`, `LEVEL_MODE` | `[0, 1]`, `direct` | `server_start` setzt `[0]` nur als Platzhalter und sendet null |
| `CONDITION_ID`, `USE_SERVER_CONTEXT` | `default`, `False` | Deploymentlabel und Nutzung beobachteter Serverdefaults |
| `INTERACTION_SCRIPT` | `[]` | Explizite geordnete Folgefragen; Historiencheckbox nur mit Skript aktivierbar |
| `ALLOW_UNVERIFIED_CASES`, `ALLOW_TASK_DERIVED_CASES` | `True`, `True` | Opt-ins fuer kontrollierte synthetische Empirie, kein Verifizierungsnachweis |
| `FETCH_SERVER_CONFIGURATION` | `False` | Nur in `live` explizit autorisierter Config-GET, unabhaengig von Generatorfreigabe |
| `EXPECTED_CONFIG_FILE` | leer | Offline Public-Snapshot laden; keine Secretdatei |
| `EXECUTE_LIVE` | `False` | Gate fuer Tutor-Generierung in `live`, zusaetzlich explizites `MODEL` |
| `EXECUTE_JUDGE_LIVE`, `JUDGE_MODEL` | `False`, `None` | Separater Judge-Gate und expliziter unterschiedlicher Alias |
| `JUDGE_RUN_ID`, `JUDGE_RESUME`, `JUDGE_RETRY_FAILED` | `judge-001`, `False`, `False` | Unveraenderliche Judgeplanung und bewusste Fortsetzung/bekannte HTTP-Retries |
| `JUDGE_COMPARE_HUMANS` | `False` | Separate Abweichungstabellen, keine Ratingaggregation |
| `COMPARE_RUN_DIRS` | `[]` | Offlinevergleich weiterer gespeicherter Bedingungen |

`CUSTOM_FLAGS` aktiviert im Default Task/Antwort, Diagnose/Feedback und
Lernziele, aber keine in diesen Tasks fehlenden `math_rules`. Der JSONL-Katalog
hat weiterhin die 12 Fixtures; `CASE_IDS` passend zur gewaehlten Quelle setzen.
Keine Aenderung am Produktions-`.env` oder an Serverregeln durch Notebookfelder.
Der geschuetzte Config-GET ist Netzwerk, aber kein LLM-Aufruf; Demo und Analyze
unterdruecken ihn auch bei gesetztem Fetchflag.

`prepare_run` friert auch Task-/Schemaquellen, optionalen Public-Snapshot und
Bedingungs-/Skriptidentitaet ein. Ohne Skript ist Historie weiterhin unzulaessig.
Notebook-`protocol_version` ist jetzt `eval-protocol-2`; bestehende
`pilot.json`/`context_core.json` behalten ihre eigene `eval-protocol-1`-Identitaet.
Studienabschnitte und API-`stage="diagnostic"|"hint"` nicht gleichsetzen.
Demo schreibt feste handgeschriebene Stage-0-/Hintausgaben; `server_start`
bleibt `not_executed`, weil keine Startwahl/Adaption erfunden wird. Eine lokale
Preview wird nur fuer direkte initiale Stufen mit expliziten Flags erstellt,
nicht fuer Serverstart, Serverdefaults oder abhaengige Chathistorie.

Committete Notebooks muessen output- und execution-count-frei bleiben;
untrusted Texte in HTML escapen. Teststatus im konkreten Testlauf feststellen,
keine globale Passzahl aus vorhandenen Zellen ableiten.

`MODE='analyze'` dispatcht nicht, kann bei Run All aber Checks und abgeleitete
Dateien neu schreiben. Das ist nicht strikt read-only: passende Quellen und
Policyhashes sind weiterhin notwendig. Notebook-Snapshots koennen ohne die
urspruenglichen Eingabepfade analysiert werden; CLI-Runs brauchen die im
Manifest referenzierten Inputs. Der aeltere `auswertung.ipynb`-Pfad arbeitet
noch teilweise CWD-relativ und mit eigenen Aggregationen; fuer belastbare
Bedingungs-/Modellmetriken `report.py` verwenden, nicht dessen historische
Tabellen mit aktuellen Reports gleichsetzen.

### Taskableitung

Zusaetzlich zum Beispielkorpus mit 12 Faellen gibt es 15 authored Faelle aus
den zwei lokalen Tasks: 9 fuer `-5*exp(x^2-2*exp(x))`, 6 fuer `x^2*sin(x)`.
`evaluation_examples` nennt je Task genau eine feste Funktion passend zur
lokalen `model_solution`. Ableitung erfindet keine Funktion, keinen Fehlerkey,
keine Punktzahl und keinen Seed. Tasks ohne Beispiele werden validiert,
tragen jedoch keine Faelle bei. Herkunft:
[../tasks/README.md](../tasks/README.md).

```bash
# Offline, vorhandenen Zielordner verwenden; keine existierende Datei ersetzen.
python -m evaluation cases-from-tasks --tasks-dir tasks \
    --output evaluation/imports/task_cases.jsonl
```

Die gelieferten Protocol-2-Presets verwenden diesen Exportpfad. Fuer CLI-Aufrufe
den Korpus dennoch explizit angeben:

```bash
python -m evaluation validate --cases evaluation/imports/task_cases.jsonl --experiment evaluation/experiments/rule_comparison.json
python -m evaluation plan --cases evaluation/imports/task_cases.jsonl --experiment evaluation/experiments/rule_comparison.json --run-dir evaluation/runs/rules-001
```

`rule_comparison.json` umfasst direkte Stufen 0..4 und vier Kontextprofile.
`start_comparison.json` nutzt die serverseitige fixe/individuelle Auswahl;
`adaptation_comparison.json` ein explizites Zwei-Turn-Skript. Die Presets sind
ausfuehrbare Pilotplaene, keine durchgefuehrte Studie oder optimierte Konfiguration.
Vor Bedingungenvergleichen je Deployment einen eindeutigen `condition_id`,
Modellalias und einen beobachteten erwarteten Konfigurationshash festlegen.
Das jeweilige Serversecret fuer geschuetzte Preflights/Simulation setzen; Planung
bleibt ohne Netzwerk. Der Notebookstandard ist kleiner als das volle Presetraster.

Export bleibt `readiness="draft"`, `response_origin="synthetic_fixture"`,
beide Verifizierungen `pending`, Score/Seed `null`. `expected_error` ist
authored synthetischer Kontext, keine ausgefuehrte PRT-Diagnose; Fehlertitel
sind entsprechend markiert. Faelle brauchen fuer Planung/Live zwei separate
Opt-ins: `allow_task_derived_cases=true` und `allow_unverified_cases=true`.
Ein erwarteter Fehler darf in `provided` gegeben oder in `model` nur als
unabhaengig zu untersuchende Hypothese bewertet werden. Gleichheit mit einer
synthetischen Referenz ist Konsistenz, kein objektiver Gradingnachweis.

Die erste kontrollierte empirische Untersuchung braucht keine verifizierten
PRTs; pending-Mathematikreferenzen und erwartete Fehler bleiben Hypothesen.
Wer spaeter verifizierte Mathematik/PRT-Bewertung beansprucht, braucht passende
Evidenz und `allow_unverified_cases=false`. Dessen Gate prueft derzeit
`mathematics_status="verified"`; Diagnoseprovenienz ist zusaetzlich zu reviewen,
nicht unabhaengig von der Suite verifiziert. Pendingdaten niemals umetikettieren.

### CLI

```bash
# 1) Korpus/Experiment prüfen (offline)
python -m evaluation validate --experiment evaluation/experiments/pilot.json

# 2) Plan + Manifest erzeugen (offline, deterministisch)
python -m evaluation plan --experiment evaluation/experiments/pilot.json \
    --run-dir evaluation/runs/pilot-001 --base-url http://127.0.0.1:8000

# 3) Nur mit expliziter Freigabe: Liveausgaben, 80 gewichtete Einheiten/h als Default
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live
# Fortsetzen nach Abbruch / Budget-Ende:
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live --resume

# 4) Automatische Prüfungen
python -m evaluation check --run-dir evaluation/runs/pilot-001

# 5) Bewertung: neutraler Bogen -> ausgefüllte CSV importieren
python -m evaluation review-export --run-dir evaluation/runs/pilot-001
python -m evaluation review-import --run-dir evaluation/runs/pilot-001 --file bewertungen.csv

# 6) Auswertung
python -m evaluation report --run-dir evaluation/runs/pilot-001
```

`plan` braucht ein neues leeres Runverzeichnis und dispatcht nichts. `--cases`
und `--profiles` bleiben massgeblich: die CLI uebernimmt `corpus_file` aus
einem gewaehlten Experiment nicht automatisch als Korpusargument. Fuer
Taskableitung etwa `--cases evaluation/imports/task_cases.jsonl` und ein
passendes separates Experiment angeben. `context_core.json` wartet auf den
verifizierten Korpus; doppelte Kontroll-/Hauptrasterzellen werden abgewiesen.

### Zugriff und Judge

Serverseitig bleiben Evaluationsrouten per `EVALUATION_API_ENABLED=0`
deaktiviert (`404`). Aktiviert: nichtleerer `EVALUATION_API_TOKEN` erforderlich,
bei fehlendem/falschem Header `X-Evaluation-Token` HTTP 401. Auf dem Client
heisst die Umgebungsvariable **`TUTOR_EVALUATION_TOKEN`**, nicht
`EVALUATION_API_TOKEN`; niemals Tokenwerte in Request-URLs, Snapshots oder
Notebooks speichern. Der Token authentifiziert Evaluation, nicht den Provider.

`GET /api/evaluation/config` liefert geheimnisfreien Tutor-Snapshot/hash sowie
Judge-`rule_id`, `judge_model`, `judge_parameters`. Es macht keinen
Provideraufruf. Der Judge ist optional und startet nie implizit nach einer
Generierung oder einem Report. Server-`EVALUATION_JUDGE_MODEL` hat absichtlich
keinen Defaultalias, muss vor Nutzung explizit gesetzt und erlaubt sein.
Defaultparameter sind Temperatur `0.0`, Max-Tokens `1200`;
aktuelle Judge-Regel-ID ist `judge-rubric-1.0-v2`.

Die Judgefunktionen sind aktuell Python-API, keine zusaetzlichen CLI-Subcommands:

```python
from pathlib import Path
from evaluation.judge import prepare_judge_run

run_dir = Path("evaluation/runs/pilot-001")
manifest = prepare_judge_run(
    run_dir, "judge-001", judge_model="explicit-distinct-allowed-alias"
)
```

`prepare_judge_run` ist offline und friert nur neueste erfolgreiche
`live_tutor_api`-Ausgaben, gemeinsame Korpusreferenzen und Requestpayloads ein.
Beispielalias bewusst ersetzen; Vorbereitung prueft keine Live-Allowlist.
Ohne gespeicherte Erfolge, Korpusreferenz oder vollstaendige Policy wird
abgebrochen. `execute_judge_run(..., execute_live=True)` verlangt eigene
Livefreigabe, gueltigen Clienttoken, aktivierten Server und einen **anderen**
Alias als den bekannten Generatoralias jedes Targets. Ein neuer Judge-Run-ID
ist unveraenderlich; Resume pinnt die beobachtete Judgekonfiguration separat.

Offlineauswertung **nach** gespeicherter autorisierter Judgeausfuehrung:

```python
from evaluation.judge import summarize_judgements

summary = summarize_judgements(run_dir, "judge-001", compare_humans=True)
```

Ein nur vorbereiteter Judgeplan kann Abdeckung/fehlende Bewertungen berichten,
ist jedoch selbst noch keine Modellbewertung.

Der Judge bekommt Task/Antwort, gemeinsame Referenzhypothese, gemeldete
Verifizierung, die konkrete Zielantwort mit SHA-256, effektive Stufe/Policy,
Modus/Phase und echten beobachteten Generatorkontext. Referenz und Sichtbarkeit
sind getrennt: nicht an den Generator gesendete Referenzen bleiben moegliche
Bewertungsdaten, nicht behaupteter Promptkontext. Fehlende echte
`prompt_messages` werden nie durch Requestfelder oder lokale Preview ersetzt.
Ein gespeicherter Manifestpolicyeintrag wird als `saved_manifest_not_observed`
markiert, nicht als beobachtete aktive Regel ausgegeben.

Judge v2 erhaelt auch separate `diagnosis_hypothesis`, `current_message`,
`turn_index` und `generator_rule_settings` (`diagnosis_mode`,
`ask_activating_question`, `hide_hint_level`, `enforce_word_limit`). Fehlende
Regelsettings bleiben unbekannt, nicht automatisch aktiv. Die gemeinsame
Referenz gilt fuer die urspruengliche Initialantwort; eine Folgeantwort wird
durch `current_message` nicht nachtraeglich mit diesem Fehlerlabel gegradet.
Requestmessage und separate Hypothese ersetzen keinen fehlenden beobachteten
Generatorprompt. `diagnosis_match` beurteilt bevorzugt die separate Hypothese,
sonst eine explizite Diagnose im Hint, sonst fehlend/nicht anwendbar.

Judgeantworten enthalten fuenf separate Likert-, sechs Kategorie-Kriterien,
optional `diagnostic_question_quality`/`diagnosis_match`, Begruendung und
Textbelege; alle Werte duerfen bei fehlender Evidenz fehlen. Auf Stufe 0 geht
es um diagnostische Fragequalitaet statt rechnerischer Hinteskalation.
`general` aktiviert keine Tutor-Stufenpolicy; nichtanwendbare Kriterien
explizit als `nicht_anwendbar` behandeln, fehlend als `null`, Unsicherheit
als `unklar`. Kein erfundener PRT-Nachweis und keine Gesamtpunktzahl.

HTTP-Fehler, ungueltiges JSON, Target-/Configdrift und Transportambiguitaet
bleiben technische Judgeattempts, keine guten Ratings. Bekannte HTTP-Fehler
brauchen `retry_failed=True`; ambigue/ungueltige Attempts werden nie replayed.
Judgeerfolge werden nicht erneut bewertet. Rohantwort, echte Judge-Messages,
Timing, Parameter und unbekannte Providertelemetrie werden getrennt gespeichert.

`summarize_judgements` schreibt nur Judgekennzahlen. `compare_humans=True`
liefert gepaarte kriteriumsbezogene Differenzen zum selben Targetattempt;
es importiert, ersetzt oder mittelt keine Expertenratings. Aliasverschiedenheit
beweist weder statistische Unabhaengigkeit noch Kalibrierung des Zweitmodells.
Judgeberichte und Human-Abweichungstabellen trennen jetzt `condition_id` und
`turn_index`; unterschiedliche Dialogschritte werden nicht gemeinsam gewertet.

## Artefakte und Reports

```text
manifest.json, plan.jsonl                        Input-, Quellen-, Plan-/Bedingungshashes
inputs/cases.jsonl, profiles.json, experiment.json  Notebook-/vorbereitete Snapshots
events.jsonl, generations.jsonl                  Generatorstarts, Fehler und tatsaechliche Outputs
checks.jsonl                                    pass/fail/inconclusive/not_applicable
reviews/review_packet.csv, review_mapping.json   Neutraler Humanbogen und verborgenes Mapping
reviews/ratings.jsonl                            Nur validierte menschliche Ratings
derived/summary.csv, paired_comparisons.csv, report.md  Generator-/Humanreport
reviews/judge/<ID>/manifest.json, inputs/         Unveraenderliche Judgeplanung und Targets
reviews/judge/<ID>/runtime_configuration.json     Separat beobachtete Judgeidentitaet
reviews/judge/<ID>/events.jsonl, judgements.jsonl  Separate Judgeattempts/Outputs
reviews/judge/<ID>/derived/judge_summary.csv      Modellratings mit eigenen Nennern
reviews/judge/<ID>/derived/expert_disagreements.csv  Optionale Human-Abweichungen
reviews/judge/<ID>/derived/judge_report.md        Getrennter Judgebericht
```

CLI-Runs referenzieren ihre angegebenen Inputs; `inputs/` ist nicht bei jedem
CLI-Plan automatisch ein archivierter Quellenbestand. Hashes sind keine
Sourcecodekopien. Judge- und aktuelle Runs verlangen passende Quellen/Inputs;
bei Aenderungen neue Runs anlegen, nicht gespeicherte Hashes reparieren.

`report.py` verwendet nur neueste erfolgreiche Liveantworten je Job fuer
Content, alle gescheiterten Attempts bleiben technisch. Humanratings werden
als `rating_source="human"` getrennt gehalten; als Judge deklarierte Ratings
werden nicht in menschliche CSVs importiert. Teilrating, leerer Wert,
Unsicherheit und Nichtanwendbarkeit erhalten eigene n/N; keine kompensierende
Gesamtnote. Mathematische Sicherheit wird nicht mit Sprachqualitaet verrechnet.

Gruppen trennen `condition_id`, Modell, Profil, effektive Stufe, Phase, Turn,
Policy-Modus, Startwahl und Skripthash. Ein Vergleich gegen `base` paart nur
denselben Fall/Start/Modell/Wiederholung/Turn/Skript innerhalb der Bedingung.
`compare_runs([reference_run, condition_run, ...])` paart verschiedene
Bedingungen offline anhand gleicher Caseidentitaet und denselben Designkeys;
effektive adaptive Stufen/Phasen sind Outcomes, keine erzwungenen Matchkeys.
Fehlende Responses/Ratings und nicht passende Zellen bleiben explizit;
Wiederholungen und Turns sind keine unabhaengigen Aufgaben.

Checks nutzen beobachtete aktive Policy/Flags, kontrollieren Konfigurations-
und Responseidentitaet sowie Referenz-Doppelfreigaben. Wortzahl/Stufennennung
sind `not_applicable`, wenn die entsprechende Regel deaktiviert oder `general`
aktiv ist. Kein positiver Endantworttreffer bleibt `inconclusive` mit
unbekannter Anwesenheit; Literalmatching und begrenztes SymPy sind weder
vollstaendige LaTeX-/Derivationsdetektion noch Produktions-Loesungsfilter.

## Kern-Semantik im Überblick

- **Manifest**: eingefrorene Hashes von Experiment, Korpus, Profilen,
  Policy und Quellcode; `--resume` bricht bei Abweichung ab.
- **Journal (`events.jsonl`)**: jeder Versuch wird vor dem Versand
  registriert; ein Abbruch nach Versand erzeugt `transport_ambiguous`
  und wird bei Resume nicht wiederholt.
- **Budget**: Dispatchte Kosten 4/2 mit 80 Einheiten/h als Default und
  separatem Generatorrequestlimit; Fehler/offene Attempts zaehlen mit.
  Keine Quotaueberwachung anderer Providerkeynutzer.
- **Verifizierung**: `allow_unverified_cases=false` schliesst unverified
  Mathematik aus. Synthetische Livepiloten bleiben kontrollierte Hypothesen,
  Offline-Demos bleiben ganz aus den Forschungskennzahlen ausgeschlossen.
- **Fachliche Eignung**: fehlende Diagnose/Feedback/Regeln/Schritte
  schließen das betreffende Profil für den Fall aus; kein Fallback auf
  kleinere Kontexte.
