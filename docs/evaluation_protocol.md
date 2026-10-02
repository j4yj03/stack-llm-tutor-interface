# Evaluationsprotokoll (eval-protocol-2)

**Status: aktueller Untersuchungsentwurf, 2026-10-02.** Dieses Protokoll ersetzt
`eval-protocol-1` fuer neue empirische Bedingungen. Es dokumentiert keine
durchgefuehrte Studie und keine erzielten Modell-, Lern- oder Motivationseffekte.
Alte Manifeste und Experimentdateien behalten ihre urspruengliche Protokollversion.

Die [Dokumentationsuebersicht](README.md), die
[datierte Expose-Ergaenzung](expose.md) und die
[Literaturnotizen](literatur/literatur.md) ordnen diesen Stand ein. Technische
Bedienung: [Evaluationspaket](../code/evaluation/README.md). Bei Abweichungen
zwischen aelteren Bediennotizen und dem hier beschriebenen Stand die genannten
Quellmodule und die tatsaechlich zurueckgegebene Serverkonfiguration pruefen.

## 1. Untersuchungsziel

> Welche Kombination aus Aufgabenkontext, Diagnosemodus, generischen Tutorregeln,
> Generierungsparametern und Start-/Anpassungsstrategie liefert auf kontrollierten
> konkreten Aufgabenantworten passende, verstaendliche und angemessen dosierte
> Unterstuetzung?

Der erste empirische Schritt benoetigt **keinen PRT**. Er vergleicht reale
Tutor-API-Ausgaben auf einer synthetischen, aufgabenabgeleiteten Fehlerbank.
Erwartete Fehler und Referenzloesungen sind kontrollierte Referenzhypothesen,
keine bereits erwiesenen STACK-Ergebnisse. Eine LLM-Diagnose wird unabhaengig
vom bereitgestellten Fehlerkontext untersucht und bleibt eine unsichere Hypothese.

Gegenstand sind beobachtbare Antworten, Regelbefolgung, Offenlegungsindikatoren,
Diagnosekonsistenz und Skriptdialoge. Nicht nachgewiesen werden Lernwirksamkeit,
Motivation, reale Bearbeitungsverbesserung, PRT-Genauigkeit, allgemeine
mathematische Zuverlaessigkeit oder Moodle-Betriebsreife.

Tutorregeln sind **Untersuchungsvariablen**, keine unveraenderliche didaktische
Wahrheit. Ergebnisse duerfen spaetere Betriebsvorgaben begruenden. Innerhalb eines
Laufs bleiben die ausgewaehlten Regeln und Referenzen fest; jede neue Bedingung
erhaelt eine neue Identitaet. Verifizierte externe Bewertungen duerfen dabei
weiterhin nicht durch das LLM ueberschrieben werden.

## 2. Fallbank und Evidenz

Ein Fall verbindet eine konkrete Funktion, eine konkrete Eingabe und eine
passende Referenz. Der optionale Task-Block `evaluation_examples` definiert
`instance_id`, `function` und `answers`; jede Antwort hat `case_id`,
`student_answer`, erwartete Validitaet/Korrektheit und optional `expected_error`.
Die Funktion muss zur festen lokalen `model_solution` derselben Aufgabe passen.
Der Export erratet weder eine Funktion aus der Antwort noch einen Fehler aus
einem LLM-Text. Schema-Gueltigkeit beweist diese mathematische Passung nicht.

Modul-/Datenpfade ohne Praefix sind im Folgenden relativ zu `code/`.

Aktuell enthalten die zwei Task-Dateien **15 synthetische Faelle**:

| Task-Instanz | Explizite Funktion | Faelle |
|---|---|---:|
| `task-chain-exp-f1` | `f(x)=-5*exp(x^2-2*exp(x))` | 9 |
| `task-prod-f1` | `f(x)=x^2*sin(x)` | 6 |

Darunter sind zwei korrekte Kontrollen, zwei Syntaxkontrollen, zwei
`unknown_error`-Szenarien und neun spezifische Fehlerantworten. Korrekte
Kontrollen haben `expected_error=null`; fehlender Fehlerkontext wird nicht
automatisch zu einer Diagnose oder einem Score von null Punkten.

Der vorhandene `evaluation/data/example_cases.jsonl` mit 12 Faellen zu vier
Instanzen ist ein **anderer**, aelterer Fixture-Korpus. Nicht still mit der
Task-Fehlerbank zusammenfuehren oder als dieselben 15 Faelle zaehlen.

Der Task-Export in `evaluation/task_cases.py` setzt `readiness="draft"`,
`response_origin="synthetic_fixture"`, Tags `task_derived`/`synthetic` sowie
Mathematik- und Diagnosestatus `pending`. Fuer deren bewusste Nutzung sind
`allow_task_derived_cases=true` und `allow_unverified_cases=true` erforderlich.
Diese Freigaben erlauben die kontrollierte Untersuchung; sie erzeugen keine
Verifikation. Bestehende `pending`-Status und fehlende Evidenz bleiben erhalten.

Der zentrale Payload-Builder normalisiert die synthetische Herkunft auf den
API-zulaessigen Wert `diagnosis_source="synthetic"`, wenn Diagnose/Feedback
uebertragen werden; bei deren Ausblendung bleibt die Herkunft im Payload leer.
Das gilt auch fuer direkt per CLI exportierte Taskfaelle, nicht nur im Notebook.
`response_origin="synthetic_fixture"` und die offene Evidenz werden dadurch
nicht veraendert oder zu einer PRT-Herkunft umgedeutet.

Eine unabhaengige manuelle oder SymPy-gestuetzte Referenzpruefung ist optional
und empfehlenswert. Nur tatsaechlich durchgefuehrte Pruefungen mit Methode,
Version, Annahmen, Ergebnis, Pruefperson und `evidence_refs` dokumentieren.
Mathematische Aequivalenz allein verifiziert keinen didaktischen Fehlergrund,
keine STACK-Eingabevaliditaet und keinen PRT-Pfad. Eine spaetere STACK-Pruefung
ist eine eigene Evidenzquelle, kein nachtraeglich erfundenes Herkunftslabel.

`tutor_context` ist der verfuegbare Datenpool; `evaluation_only` enthaelt
gemeinsame Referenzen, erwartete Labels, Evidenz und Provenienz. Erwartete Labels
gehen nicht als versteckte Loesung an die unabhaengige Diagnosebedingung.
Referenzschritte und Endloesung gelangen nur bei der ausgewaehlten Kontextoption
und aktiven Stufenfreigabe in den Generatorprompt. Beim Schritteprofil darf die
passende Endloesung als interner Literal-Guard im API-Payload stehen, ohne als
Referenzabschnitt im Prompt sichtbar zu sein. Evaluatoren erhalten fuer alle
verglichenen Bedingungen dieselbe Referenz derselben Instanz.

## 3. Variablen und Defaults

Untersucht werden nicht nur Kontext-Checkboxen. Vor jedem Vergleich muessen die
vollstaendige Bedingung, die beabsichtigte Aenderung und unveraenderte Groessen
feststehen. Die aktuelle Serverkonfiguration ist in `app/config.py`,
`app/hint_policy.py` und `app/runtime_config.py` umgesetzt.

| Bereich | Konfigurierbare Groessen |
|---|---|
| Kontext | Alle zehn `ContextOptions`, verfuegbare Task-Felder, `CONTEXT_OPTIONS`, separate `TUTOR_STAGE0_CONTEXT_OPTIONS`, Historienlimit |
| Diagnose | `TUTOR_DIAGNOSIS_MODE=provided\|model\|none`, Herkunft und Unsicherheit des gelieferten Fehlerkontexts |
| Tutorregeln | `TUTOR_RULES_ID`, `TUTOR_POLICY_MODE=tutor\|general`, `TUTOR_ASK_ACTIVATING_QUESTION`, `TUTOR_HIDE_HINT_LEVEL`, `TUTOR_ENFORCE_WORD_LIMIT` |
| Stufenpolicy | Pro Stufe `name`, `goal`, `may_include`, `must_not_include`, `max_words`, Schritte-/Endloesungsfreigabe und `max_solution_steps` |
| Generierung | `LLM_MODEL`, `LLM_ALLOWED_MODELS`, `LLM_API_MODE`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_DISABLE_THINKING`, `LLM_TIMEOUT`, `LLM_RETRY_DELAY` |
| Format | `TUTOR_RESPONSE_FORMAT=text\|structured`; strukturierte Ausgabe trennt `hint` und `diagnosis_hypothesis` |
| Start | `TUTOR_START_MODE=fixed\|individual`, `TUTOR_START_LEVEL`, explizite Zielstufe oder serverseitige Auswahl |
| Anpassung | `TUTOR_ADAPTIVE_ENABLED`, `TUTOR_ADAPTIVE_AFTER_SECONDS`, `TUTOR_ADAPTIVE_CONFUSION_PHRASES`, `TUTOR_ADAPTIVE_STEP`, `TUTOR_ADAPTIVE_MAX_LEVEL` |

Die bestehenden Betriebsdefaults bleiben bis zu einer expliziten Auswahl:
Start `fixed` auf **1**, Diagnose `provided`, Policy `tutor`, Antwort `text`,
Adaptation **aus**. Die Standardpolicy hat Stufen **0 bis 4**, wobei 0 eine kurze
diagnostische Frage mit konfigurierbarem Kontext ist. `MIN_HINT_LEVEL=0` ist
fest, `MAX_HINT_LEVEL` ist konfigurierbar und standardmaessig 4. Eine andere
Obergrenze benoetigt vollstaendige passende Policies und muss zu Clientgrenzen
passen; das Evaluationsmodell begrenzt geplante Stufen derzeit zusaetzlich auf 32.

Der Defaultkontext enthaelt Aufgabe, Antwort, Diagnose, Feedback, Lernziele,
Loesungsschritte, Endloesung und Historie; Score und mathematische Regeln sind
standardmaessig aus. Die Referenzfelder bleiben trotz dieser Defaults an die
Doppelpruefung gebunden. Die Stage-0-Kappung erlaubt standardmaessig nur Aufgabe,
Antwort, Lernziele, mathematische Regeln und Historie, schaltet aber kein
zuvor deaktiviertes Feld ein.

Policy-Datei und Overrides (`HINT_LEVELS_PATH`, `TUTOR_HINT_POLICY_JSON`,
`TUTOR_LEVEL_<n>_<FELD>`) sind Bedingungen auf der isolierten Serverinstanz,
keine beliebigen Systemprompt-Overrides im Tutor-Request. Ein `rules_id` allein
beweist keine Gleichheit; Inhalt und Konfigurationshash sind entscheidend.

`provided` nutzt nur tatsaechlich sichtbaren Fehlerkontext. `model` und `none`
unterdruecken Diagnosecode und Feedback im effektiven Kontext. In `model` darf
eine unsichere Diagnosehypothese aus sichtbaren Daten entstehen; sie ist kein
Score, verifiziert keine tatsaechliche Punktzahl und ist keine autoritative
Bewertung. Fuer eine getrennte maschinenlesbare
Hypothese `structured` verwenden und das Format in den Vergleichsarmen gleich
halten. Bei ausgeschalteter Historie bleibt die **aktuelle Nachricht** im Prompt;
`include_chat_history=false` bedeutet nicht, die aktuelle Rueckfrage zu ignorieren.

Die Kontextoptionen sind `include_question_text`, `include_student_answer`,
`include_diagnosis_code`, `include_prt_feedback`, `include_score`,
`include_learning_goals`, `include_math_rules`, `include_solution_steps`,
`include_final_answer` und `include_chat_history`. Die bestehenden Profile
`base`, `diagnosis`, `feedback`, `diagnosis_feedback`, `knowledge`, `steps` und
`solution` sind Daten-/Flagspezifikationen, nicht bereits ausgewaehlte optimale
Kontextregeln. Die Task-Fehlerbank liefert derzeit keinen Score und keine
`math_rules`; entsprechende Profile sind ohne explizit authorierte weitere
Daten nicht fuer alle Faelle ausfuehrbar. Kein Score von 0 oder eine vermutete
Regel wird eingesetzt, nur um ein Profil zugelassen zu bekommen.

## 4. Versuchsblöcke

Die folgenden vier Bloecke sind ein **Design**, keine bereits durchgefuehrten
Experimente und kein vollfaktorielles Raster aller Parameter. Fallumfang,
Wiederholungen, Auswahlregeln, primaere Kriterien und Budget vor Live-Ausfuehrung
festlegen. Bei kleinen Instanzzahlen nur deskriptiv und mit Abdeckungsangaben
berichten; mehrere Antworten derselben Funktion sind keine unabhaengigen Aufgaben.

### Block A: Stufenpilot und Start

Zuerst unter einer expliziten Ausgangskonfiguration alle Standardstufen **0, 1,
2, 3, 4** auf ausgewaehlten Initialantworten testen. Stufe 0 erhaelt ihren
tatsaechlichen, separat begrenzten Kontext und wird als diagnostische Frage
bewertet, nicht als besonders schwacher Rechenhinweis. Kriterien sind unter
anderem Zielbezug, Informationsgewinn, Nicht-Suggestivitaet und Aktivierung.

Auf einem vorab benannten Entwicklungs-/Pilotteil eine **gemeinsame feste
Baseline-Stufe** nach dokumentierter Auswahlregel bestimmen. Diese empirische
Baseline ist nicht automatisch der aktuelle Betriebsdefault 1 und nicht das
Kontextprofil `base`. Die Auswahl beruecksichtigt mathematische Risiken,
Offenlegung und Hilfreichkeit getrennt, statt eine kompensierende Gesamtnote
zu maximieren. Auswahl und Regel danach einfrieren.
Split, Auswahlkriterien und Entscheidungsregel vorab festlegen. Die Baseline
wird anschliessend **manuell** anhand ausgewaehlter Pilotbelege bestimmt und
mit deren Run-/Attempt-Identitaet und Begruendung dokumentiert. Es gibt kein
implementiertes Werkzeug zur automatischen Baselineoptimierung und derzeit
keine als empirisch optimal belegte Startstufe.

Auf einem unberuehrten Held-out-Teil den gewaehlten gemeinsamen Start mit
`individual` vergleichen: gleiche Initialantworten, Datenverfuegbarkeit,
Generatoralias und Regeln, aber serverseitige Startentscheidung pro Antwort.
Beide Arme nutzen `level_mode="server_start"` und senden keine explizite
Startstufe. `hint_levels=[0]` ist hierbei nur ein Planplatzhalter, **kein**
beobachteter Start auf Stufe 0. Der feste Arm verwendet die ausgewaehlte
`TUTOR_START_LEVEL`; der individuelle Arm protokolliert Auswahl, Begruendung und
`start_prompt_messages`. Eine explizite Request-Stufe umgeht die Modellauswahl.

Die individuelle API-Startwahl verwendet die **angeforderten Kontextoptionen**,
begrenzt durch Stufe-0-Caps und Diagnosemodus; sie greift nicht auf globale
HTML-Kontextoptionen zurueck. Ohne eigene API-Optionen gelten die konfigurierten
Defaults. Den separaten Auswahlprompt `start_prompt_messages` und seine
`start_decision.context_options` getrennt vom Generierungsprompt pruefen.
`start_selection_context` kontrolliert beobachtete Auswahloptionen und gesperrte
Kontextteile; fehlende Evidenz bleibt `inconclusive`. Rueckgegebene
`baseline_hint_level`, Startentscheidung und effektive Stufe berichten,
nicht aus dem Plan raten.
Die Modellstartwahl ist eine heuristische Unterstuetzungsentscheidung aus
Initialantworten, kein validiertes Modell des individuellen Lernstands.

Mit nur zwei Task-Instanzen kann ein instanzweise getrennter Held-out-Vergleich
sehr klein sein. Ein reiner Antwortsplit derselben Funktion verhindert keine
Instanzleckage. Split-Einheit und diese Grenze offen benennen; fuer staerkere
Generalisierung zusaetzliche explizite, referenzpassende Instanzen authoren.

### Block B: Diagnose und Regelkontraste

Den unabhaengigen Modus `model` mit `provided` und optional `none` vergleichen.
In `model` muessen erwartetes Fehlerlabel und daraus abgeleitetes Feedback im
**beobachteten** Generator- und gegebenenfalls Startprompt fehlen. Referenzloesung
und Fehlerhypothese bleiben als gemeinsame Bewertungsbasis erhalten. Falls ein
zusaetzlich sichtbarer Loesungskontext untersucht wird, ihn in beiden Armen gleich
halten und als solchen ausweisen. Labelkonsistenz ist keine PRT-Treffergenauigkeit.

Die Standardkappung fuer Stufe 0 blendet Diagnosecode/Feedback auch im
`provided`-Arm aus. Ohne beobachteten Sichtbarkeitsunterschied ist das kein
Diagnosekontrast. Eine Freigabe dort muss als eigene Bedingung deklariert werden;
andererseits koennen spaetere Stufen den eigentlichen Labelkontrast abbilden.

Anschliessend wenige begruendete Regel-/Kontextkontraste gegen die eingefrorene
Baseline vorsehen, beispielsweise aktivierende Frage an/aus, kuerzere Wortgrenze,
eine andere Stufenziel-Formulierung, Schritte-/Referenzzugang, Historie im Dialog
oder angepasste Temperatur/Tokenobergrenze. Saemtliche in Abschnitt 3 genannten
Parameter sind pruefbar; nicht alle gleichzeitig kreuzen. Pro Kontrast eine
definierte Aenderung oder ein ausdruecklich benanntes Regelpaket, neue
`condition_id`, neue Serverkonfiguration und gepinnte Identitaet verwenden.

Ein Datenfeld im Payload, eine aktivierte Checkbox oder der Name eines Profils
ist noch kein Beleg fuer Sichtbarkeit. Angeforderte Optionen, effektive Optionen
und echte `prompt_messages` vergleichen. Fehlende Lernziele, Regeln, Score oder
Referenzen fuehren zu dokumentierten Ausschluessen, nicht stillen Ersatzdaten.

### Block C: Feste und adaptive Interaktion

Den gemeinsamen, in Block A ausgewaehlten Start mit einer Anpassung bei der
naechsten Interaktion vergleichen. In beiden Armen sind Initialantwort,
Generator, sonstige Regeln, Kontext und **vollstaendiges Nachrichtenskript samt
simulierten Zeiten** identisch. Fuer den Adaptationskontrast bleibt auch die
Startstrategie gleich; ein gleichzeitiger Wechsel zu `individual` waere ein
zusaetzlicher Faktor und darf nicht als reiner Adaptationseffekt gelten.

Adaptation greift nur bei einer neuen Nachricht, wenn **Zeitgrenze erreicht UND
Verwirrungssignal vorhanden** sind. Kein Timer generiert selbststaendig Antworten
und lange Inaktivitaet allein bedeutet kein Missverstaendnis. Die Policy erhoeht
innerhalb der konfigurierten Grenze; eine explizite Zielstufenanforderung hat
Vorrang und ist ein anderer Mechanismus. Fuer den eigentlichen Vergleich keine
expliziten Folge-Zielstufen setzen.

Vorzusehende Skriptkontrollen: kurze Zeit mit Verwirrung, lange Zeit ohne
Verwirrung, lange Zeit mit Verwirrung sowie erreichte Obergrenze. Im echten Ablauf
wird das Intervall **monoton seit der letzten erfolgreichen Antwort** gemessen,
solange deren gespeicherte `clock_id` zum aktuellen Serverprozess passt.
Nach Prozessneustart oder bei einem anderen Worker bleibt das Intervall
unbekannt (`elapsed_seconds=null`); der UTC-Zeitstempel ersetzt diese Messung
nicht. Nach einer neuen erfolgreichen Antwort beginnt eine neue Messbasis.

Dieses Serverintervall kann Leerlauf enthalten und ist keine aktive Lern- oder
Bearbeitungszeit. Im Experiment ist `elapsed_seconds` eine ausdrueckliche
Simulation, kein echtes Warten. Das entsprechende API-Feld
`simulation_elapsed_seconds` erlaubt endliche Werte von 0 bis 86400 Sekunden
und erfordert ebenso wie ein gesetztes `confusion_signal` Tokenzugang.
Die Kennzeichnung `time_source="simulated"` belegt keine tatsaechliche Lernzeit;
`observed_server_interval` muss zusammen mit dem moeglicherweise fehlenden
Intervall gelesen werden. Kein Zeitablauf dispatcht selbst eine LLM-Anfrage.
Ein konfigurierter Formulierungstreffer wie "ich verstehe nicht" ist ein
Selbstberichtssignal, keine validierte Erkennung des Verstaendniszustands.

Session, `turn_index`, urspruengliche Initialantwort, Baseline-Stufe,
effektive Stufe/Phase, Zeit-/Signalquelle und Adaptationsentscheidung getrennt
protokollieren. Der Runner fuehrt Folge-POSTs nur nach erfolgreicher
Vorgaengerantwort aus. Eine im Skript spaeter vorgegebene **korrekte Antwort ist
vorherbestimmt**, keine vom Hinweis verursachte Verbesserung. Das Skript aendert
die gespeicherte Initialantwort nicht automatisch und bewertet keine neue
mathematische Eingabe. Es prueft Reaktionsverhalten, nicht Lernen oder Motivation.

### Block D: Allgemeine Modellbedingung

Eine echte allgemeine Assistentenbedingung verwendet eine Serverinstanz mit
`TUTOR_POLICY_MODE=general` und protokolliert deren tatsaechlichen Systemprompt.
Fuer den Policy-Kontrast denselben Modellalias, Task-/Antwortkontext und dieselben
Generierungsparameter verwenden; ein Modellwechsel ist ein weiterer Faktor.
Das Profil `base` allein entfernt **keine** Tutorrolle oder Hilfestufenregeln und
ist deshalb nicht die allgemeine Modellbedingung.

`general` entfernt die tutorspezifische Rollen-/Stufensteuerung, nicht die
grundlegenden Schutzregeln fuer untrusted input und externe Bewertungen. Die
technische Doppelpruefung fuer Referenzfelder bleibt bestehen. Vollstaendige
Loesungen werden auch hier als vorhanden erfasst; tutorspezifisch unzulaessiger
Loesungsverrat und Stufenangemessenheit sind ohne entsprechende tatsaechliche
generische Vorgabe nicht anwendbar. Laenge, mathematische Plausibilitaet und
Verstaendlichkeit bleiben separat vergleichbar.

## 5. Umsetzung und offene Schritte

| Gegenstand | Vorhandene Umsetzung | Noch zu tun / Grenze |
|---|---|---|
| Task-Fehlerbank | Schema, `cases_from_tasks`, CLI `cases-from-tasks`, 15 authorierte Antworten | Unabhaengige Referenzpruefung, weitere Instanzen und finaler Split |
| Regeln und Stufe 0 | Konfigurierbare Policies, Kontextkappung, Diagnose-/Format-/Start-/Adaptationsmodi | Empirische Auswahl und begruendete Betriebsvorgaben |
| Bedingungen und Dialoge | `Experiment.condition_id`, `expected_config_sha256`, `level_mode`, `use_server_context`, `interaction_script`; serieller Runner; gelieferte Regel-/Start-/Adaptationspiloten | Pilotsplits und endgueltige Block-A-D-Bedingungen authoren, Konfigurationen pinnen und empirisch ausfuehren |
| Beobachtung | Aktive Policy, Konfigurationssnapshot/hash, Start- und Adaptationsmetadaten, echte Prompts | Providerinterne Telemetrie und unabhaengige Deploymentnachweise fehlen teilweise |
| Berichte | `build_report`, `compare_runs`, neutrale Menschenratings, separate Judge-Berichte | Block-spezifische Analyse und gegebenenfalls separates menschliches Stufe-0-Raster |
| Notebook | Testbench mit `eval-protocol-2`, Taskquelle, Bedingungs-/Start-/Skriptsteuerung, Snapshots und separatem Judge-Gate; Default bleibt offline Demo | Bloecke A-D konkret authoren und pilotieren; keine automatische Baseline-Auswahl oder bereits ausgefuehrte Studie |
| Vorhandene Presets | `rule_comparison.json`, `start_comparison.json`, `adaptation_comparison.json` tragen `eval-protocol-2`; historische Presets bleiben Protocol 1 | Pilotplaene sind noch kein abgeschlossenes Studiendesign; `context_core` erwartet weiterhin einen nicht mitgelieferten Korpus |

Offline-Tests unter anderem in `test_task_cases.py`,
`test_runtime_config.py`, `test_evaluation_conditions.py` und
`test_evaluation_judge.py` pruefen technische Vertraege mit Testdoubles. Sie sind
keine Ergebnisse der Versuchsblöcke und keine reale STACK-/Providerverifikation.
Dieses Dokument ist fuer neue Terminal-/API-Laeufe die Designvorgabe; es behauptet
keine bereits ausgefuehrte neue Notebookstudie.

## 6. Durchführung und Identität

Alle Python-/CLI-Befehle aus `code/` ausfuehren. Export, Validierung und Planung
sind offline; vorhandene Credentials starten nichts von selbst. Der folgende
Export erzeugt nur einen neuen lokalen Datensatz, keine LLM-Ausgaben:

```bash
python -m evaluation cases-from-tasks --tasks-dir tasks \
    --output evaluation/data/task_cases_local.jsonl
```

Fuer neue Blockbedingungen eigene Experimentdateien mit
`protocol_version="eval-protocol-2"` und expliziten Opt-ins verwenden. Der Name
`corpus_file` in der Experimentdatei setzt die CLI-Eingabe nicht automatisch;
bei `validate`/`plan` auch `--cases` und `--profiles` passend angeben. Keine
existierenden Snapshots oder Manifesthashes aendern, um einen Resume zu erzwingen.
Mit `use_server_context=true` wird die Optionsuebergabe weggelassen, nicht der
profilspezifische Datenpool erweitert. Fuer einen fairen Serverdefault-Kontrast
muessen deshalb dieselben benoetigten Felder in beiden Payloads tatsaechlich
verfuegbar sein. Snapshot und Hash dieser Inputs vorab sichern.

Die isolierte Tutorinstanz benoetigt eine eigene `DATABASE_PATH`.
`GET /api/evaluation/config` liefert bei expliziter Aktivierung und gueltigem
`X-Evaluation-Token` eine oeffentliche Konfiguration mit `config_sha256`.
`EVALUATION_API_TOKEN` bleibt serverseitig; der Client liest
`TUTOR_EVALUATION_TOKEN` lokal. Token und API-Key nicht in Manifest, URL oder
Prompt schreiben; sie bleiben in den jeweiligen Auth-Headern, nicht in Logs
oder oeffentlichen Konfigurationssnapshots. Die echte lokale `.env` wird weder
zur Dokumentationspruefung ausgelesen noch protokolliert.
Der Snapshot kann vor Planung als `expected_config` an
`create_run` uebergeben werden; `expected_config_sha256` pinnt die erwartete
Deploymentbedingung. Generierung beginnt ausschliesslich mit ausdruecklicher
Live-Freigabe (`--execute-live` bzw. `execute_live=True`).

Die integrierte App verwendet die beim Start geladene aktive Policy fuer
Generierung, `/health` und den geschuetzten Konfigurations-GET. Aenderungen an
Env-/Policydateien erfordern einen Serverneustart mit neuer Bedingung; der GET
laedt keine abweichenden Dateioverrides nach und bietet keinen Hot-Swap.
Passende Hashes zeigen dieselbe berichtete Konfiguration, keine empirisch
ausgewaehlte oder optimierte Baseline.

Eine Session beginnt mit frischem Chat. Direkte Stufenvergleiche verwenden
explizite Ziele; Startstrategievergleiche lassen diese offen. Skript-Turns
bleiben innerhalb derselben Session und Reihenfolge; nur Sessions werden
deterministisch gemischt. Ein fehlgeschlagener Vorgaenger blockiert Folgeturns.

Zu speichern sind ausgewaehlte Inputs, Plan, Versions-/Quellfingerprints,
`condition_id`, Modellalias, Anfrageidentitaet, aktive `hint_policy`,
`configuration`, `config_sha256`, tatsaechliche `prompt_messages`, effektive
Optionen, Start-/Adaptationsentscheidungen, HTTP-Ausgang, Zeiten und Ausgabe.
Konfigurationshashes verwenden sortiertes kompaktes JSON mit `ensure_ascii=True`.
Ein lokaler Preview oder Quellhash beweist nicht die verwendete Serverkonfiguration
oder Providergewichte. API-Aliase sind keine Modelldigests; angeforderte Parameter
sind nicht automatisch bestaetigte providerinterne Einstellungen.

Alle Dispatchversuche werden vor Versand dauerhaft journalisiert. Kein
automatischer Runner-Retry und kein stiller Modellwechsel. Explizite Wiederholung
bekannter fehlgeschlagener Starts bleibt moeglich; unklare oder identitaetswidrige
Versuche werden nicht wiederholt. Fehlgeschlagene Folge-POSTs werden wegen
fehlender API-Idempotenz nicht einfach erneut gesendet: Die Nachricht koennte
bereits gespeichert sein. Generierungserfolg schreibt erst die Zielstufe fort.

Das gewichtete Standardbudget umfasst **80 Einheiten pro Stunde** fuer den
seriellen Quelllauf: Generatorversuch 4, Judgeversuch 2. Es deckt konservativ
Startauswahl plus Antwort und moegliche Client-Fallbacks ab, misst aber keine
tatsaechlichen Upstream-Aufrufe. Das zusaetzliche logische Generatorlimit ist
standardmaessig 35/h; bei Kosten 4 ist ohne Judge meist das gewichtete Limit
enger. Fehler und offene Versuche zaehlen mit. Beide Richtungen lesen Generator-
und `reviews/judge/*/events.jsonl`-Journale auch nach Neustart. Andere Runs,
gleichzeitige Clients oder sonstige Nutzung desselben Providerkeys sind nicht
abgedeckt; keine parallelen Live-Batches als Standard.

## 7. Auswertung

Ergebnisse auf getrennten Ebenen berichten:

1. Technik: alle Versuche, Fehler, blockierte Turns, HTTP-Ausgaenge und Laufzeiten.
2. Manipulationspruefung: gepinnte Serveridentitaet, aktive Regeln, angeforderter
   versus effektiver Kontext sowie ausschliesslich beobachtete Prompts.
3. Offenlegung: `complete_solution_present` getrennt von `prohibited_disclosure`;
   Literal-/Aequivalentformen und begrenzte optionale SymPy-Pruefung sind Indikatoren.
4. Menschenratings: fuenf Likert-Kriterien und sechs kategoriale Kriterien aus
   `rubric-1.0`, begruendete negative Befunde, fehlende Werte nicht als bestanden.
5. Modellratings: optionaler Judge, eigenes Quellenlabel, eigene Abdeckung und
   eigener Bericht; keine gemeinsame Skala mit Menschenratings.
6. Vergleiche: passende Fall-/Instanzidentitaet, Modell, Wiederholung, Profil,
   vollstaendiger Skripthash und Turn; Baseline-/effektive Stufe separat zeigen.

Die automatische Offenlegungspruefung ist kein vollstaendiger semantischer
Detector und kein Produktionsfilter. Kein positiver Formeltreffer bleibt
`inconclusive`, nicht Abwesenheitsbeweis. Die Prompt-Doppelpruefung bleibt auch
bei Regelkontrasten erhalten. Fuer Ausgabebefunde ist die aktive Policy massgeblich,
nicht ein hartes universelles "vor Stufe 4 verboten" bei geaenderten Regeln.

`compare_runs` vergleicht verschiedene `condition_id` gegen den zuerst
uebergebenen Referenzlauf. Effektive Stufen/Phasen sind dabei Ergebnisse, keine
Paarungsschluessel; so wird eine Adaptation nicht durch Wegfiltern unterschiedlicher
Stufen unsichtbar. Profilvergleiche innerhalb eines Laufs bleiben nach
Bedingung/Turn/Stufe/Modell getrennt. Wiederholungen und Turns sind keine
unabhaengigen Aufgaben. Teilratings, fehlende Paare und alle Nenner ausweisen.

Neutrale `review_id` und `rater_id` unterstuetzen Menschenreviews, garantieren
aber keine Verblindung: sichtbare Phase/Regeln koennen den Arm erkennbar machen.
Mappings und vorangegangene Modell-/Profilansichten nicht an blinde Reviewer
geben. Ein begruendetes separates Diagnosefragen-Raster ist fuer Stufe 0
vorzusehen; neue menschliche Kriterien nicht als schon vorhandene CSV-Felder
ausgeben. Der optionale Judge hat dafuer `diagnostic_question_quality` und
`diagnosis_match`; diese sind weiterhin nur Modellratings.

Nur reale `execution_source="live_tutor_api"`-Antworten gehen in fachliche
Generatorkennzahlen ein. Ein realer Request mit synthetischem Taskfall ist nicht
das gleiche wie eine handgeschriebene `offline_demo`-Ausgabe. Demos, Mocks und
deren Ratings/Checks bleiben ausgeschlossen. Inhaltsberichte nutzen die neueste
erfolgreiche Antwort je Job; fehlgeschlagene Versuche verschwinden nicht aus der
technischen Bilanz. Keine erfundenen Antwortzeiten, Ratings oder Gesamtqualitaetsnoten.

## 8. Optionaler Zweitmodell-Judge

Der Judge ist implementiert, aber nicht automatisch Bestandteil eines Laufs.
`POST /api/evaluation/judge` erfordert `EVALUATION_API_ENABLED=1`, ein gesetztes
`EVALUATION_API_TOKEN` und den Header `X-Evaluation-Token`; deaktiviert liefert
die Route 404, ungueltiger Zugang 401. Ein explizites
`EVALUATION_JUDGE_MODEL` und gegebenenfalls angeforderter Alias muessen erlaubt
sein. Der Client prueft, dass der Judgealias vom gespeicherten Generatoralias
abweicht. Unterschiedliche Aliase beweisen keine unabhaengigen Modellgewichte.

`prepare_judge_run` friert ausschliesslich gespeicherte erfolgreiche Live-Ausgaben
und deren gemeinsame Referenzen offline ein. `execute_judge_run` benoetigt
zusaetzlich `execute_live=True`; `summarize_judgements` berichtet separat.
Die vorhandene CLI stellt dafuer nicht automatisch eigene Judge-Unterbefehle bereit;
das Notebook hat ein eigenes, standardmaessig ausgeschaltetes Judge-Live-Gate.
Judge-Temperatur und Tokenlimit werden als `EVALUATION_JUDGE_TEMPERATURE`
und `EVALUATION_JUDGE_MAX_TOKENS` getrennt festgelegt; JSON-Mode,
Regel-ID `judge-rubric-1.0-v2`, angeforderter Alias und unbekannte
Providertelemetrie werden ausgewiesen.

Der Request bindet neutrale Review-/Zielidentitaet und SHA-256 des UTF-8-Hinweises
an begrenzte Task-, Referenz-, Policy- und Sichtbarkeitsdaten. Beliebige Prompt-
Overrides und Generator-Modelllabels sind nicht erlaubt. Task, Antwort,
Referenz, beobachteter Generatorprompt, Regeln und zu beurteilender Hinweis
bleiben getrennte untrusted Datenabschnitte. Fehlender echter Generatorprompt
bleibt `observed_context=None`; kein lokaler Ersatzpreview.
Die begrenzten optionalen Evidenzfelder `diagnosis_hypothesis`,
`current_message` und `turn_index` uebertragen die beobachtete separate
Tutorhypothese sowie die eingereichte Folgenachricht und ihren Turn. Die
Initialantwort und gemeinsame Instanzreferenz bleiben unveraendert;
eine neue Antwort in der Folgenachricht wird nicht automatisch durch das
initiale Fehlerlabel bewertet. Die Nachricht allein beweist nicht, dass sie
im Generatorprompt sichtbar war.

`generator_rule_settings` uebernimmt ausschliesslich die beobachteten
Konfigurationswerte `diagnosis_mode`, `ask_activating_question`,
`hide_hint_level` und `enforce_word_limit`, ohne Modell-/Bedingungslabels an
den Judge zu geben. Deaktivierte Regeln werden nicht als Anforderungen
angenommen; fehlende Werte bleiben unbekannt. Ein `max_words`-Policywert ist
bei ausgeschalteter Durchsetzung nicht automatisch eine Ausgabebeschraenkung.
`diagnosis_match` kann die separate, als unsicher markierte Modellhypothese
beurteilen, ohne sie allein wegen fehlender gelieferter Diagnose als erfunden
einzustufen. Das prueft Konsistenz/Plausibilitaet, nicht einen tatsaechlichen
Score oder eine objektive PRT-Diagnose.

Artefakte liegen nur unter `reviews/judge/<id>/`: Manifest/Input-Snapshots,
Journal, `judgements.jsonl`, echte Judgeprompts, erfolgreiche rohe strukturierte
Antworten und separate CSV-/Markdownberichte nach Bedingung und Turn.
Judgezugriff aendert weder Chat noch Datenbank. Negative Ratings brauchen
Begruendung; ungueltige JSON-Ausgaben,
Fehler und Unsicherheit werden nicht zu guten Bewertungen. Optionaler Vergleich
mit Menschenratings zeigt Differenzen separat und importiert keine Judgewerte
in den Expertenbogen. Auch der Judge ist keine mathematische Autoritaet.

## 9. Governance und Aussagegrenzen

TLS-Zertifikatspruefung und institutioneller Betrieb sind technische bzw.
organisatorische Voraussetzungen, **kein Nachweis rechtlicher Konformitaet**.
Vor realen Studierendendaten Rechtsgrundlage, Information/Einwilligung soweit
erforderlich, Rollen, Empfaenger, Auftragsverarbeitung, Nutzungsrechte,
Speicherfristen und Loesch-/Zugriffskonzept pruefen.

Datenspuren umfassen Moodle, Browser/GET-URLs, Webserver und Reverse Proxies,
SQLite (`DATABASE_PATH`), Tutor-/Providerlogs, Evaluationssnapshots, Prompts,
CSV-Exports und Backups. `ans1` im `/start`-GET kann in Browserhistorie sowie
Server-/Proxylogs landen; HTTPS, URL-Encoding und `noreferrer` beseitigen das
nicht. Eine UUID authentifiziert keinen Nutzer. Fuer die erste Fallbank nur
synthetische Daten ohne Personenbezug verwenden.
`DEBUG_MODE=0` betrifft die HTML-Debuganzeige, nicht den Inhalt der JSON-
Debugfelder oder des LLM-Kontexts. Der Moodle-`debug`-Schalter zur
Diagnosemarker-Uebertragung ist davon verschieden. Beide sind kein Ersatz
fuer allgemeine Zugriffskontrolle.

Der Judge ist ein zusaetzlicher Verarbeitungsschritt und gegebenenfalls
zusaetzlicher Empfaenger/Verarbeiter: Er sieht auch Referenzen und beobachtete
Prompts, die mehr enthalten koennen als der eigentliche Hinweis. Eigene
Datenminimierung, Freigabe, Budget und Aufbewahrung festlegen; nicht aus dem
Generatorzugang eine Judgefreigabe ableiten.

Live-Modelltests, reale STACK-/Moodlevalidierung, unabhaengige Referenzpruefung
und eine Lernstudie sind jeweils eigene Nachweisschritte. Die Umsetzung dieses
Protokolls oder bestandene Offline-Tests ersetzen keinen dieser Nachweise.
