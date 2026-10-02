# Ordner `code/config/`

Stand: 2026-10-02. Generische Tutorbedingungen, getrennt von aufgabenspezifischen
Daten in `tasks/`. Laufzeitquelle ist `app/config.py`; Policytexte werden in
`HintPolicy` geladen und validiert. Vorlage: [../.env.example](../.env.example).
API-Nutzung: [../app/README.md](../app/README.md); Vergleichslauf:
[../evaluation/README.md](../evaluation/README.md).

## `hint_levels.json`

Die aktive Policy braucht alle Stufen `0..MAX_HINT_LEVEL`, standardmaessig
`0..4`. `MIN_HINT_LEVEL=0` ist fest, `MAX_HINT_LEVEL` erlaubt `0..32` aus der Umgebung.
Nur aktive Stufen werden in `HintPolicy.levels` und der oeffentlichen
Konfiguration ausgegeben. Auch in der Datei vorhandene inaktive Stufen
werden validiert. Eine hoehere Obergrenze verlangt entsprechende Eintraege
in der Policydatei; Overrides erzeugen keine bisher fehlenden Stufen.

### Felder je Stufe

| Feld | Bedeutung |
|---|---|
| `name`, `goal` | Nichtleere Strings; Kurzname und generisches didaktisches Ziel |
| `max_words` | Positive Ganzzahl; Promptwortlimit bei aktiver Tutorregel, keine Ausgabetrunkierung |
| `may_include`, `must_not_include` | Listen nichtleerer Strings; erlaubte/verbotene Inhalte |
| `include_solution_steps` | Boolean; Stufenfreigabe fuer Referenzschritte |
| `max_solution_steps` | Nichtnegative Ganzzahl oder `null` fuer alle geordneten Schritte |
| `include_final_answer` | Boolean; Stufenfreigabe fuer Referenzendloesung |

Alle acht Felder sind Pflicht. Unbekannte Felder, falsche Typen und fehlende
aktive Stufen loesen `HintPolicyError` aus; es gibt keine stillen Defaults.

### Defaultprogression

| Stufe | Name | Ziel | max. Wörter | Schritte | Endlösung |
|--:|---|---|--:|---|---|
| 0 | Diagnosephase | kurze diagnostische Frage zu Verstaendnis oder Vorgehen | 70 | nein | nein |
| 1 | Orientierung | relevantes Konzept aktivieren | 70 | nein | nein |
| 2 | Strukturierung | Aufgabe zerlegen, Regel benennen | 100 | nein | nein |
| 3 | Nächster Rechenschritt | einen konkreten Schritt ermöglichen | 130 | max. 3 | nein |
| 4 | Ausführliche Unterstützung | Lösungsweg erläutern | 220 | ja | ja |

### Regeln

- Keine task-spezifischen Formeln in dieser Datei oder in generischen Overrides.
- `TUTOR_POLICY_MODE=tutor` verwendet Rolle, Ziel, Erlaubnisse/Verbote und
  aktivierte Zusatzregeln. `general` laesst diese didaktischen Vorgaben weg;
  die Referenz-Kontextfreigaben bleiben trotzdem aktiv.
- Die Flags bilden zusammen mit `ContextOptions` im Prompt-Builder die **Doppelprüfung** für Lösungspreisgabe: Ein Abschnitt erscheint nur, wenn Option **und** Stufe beide `true` sind.
- Passende Tests: `code/tests/test_hint_policy.py` und `code/tests/test_solution_disclosure.py`.

## Policy-Overrides

Die Reihenfolge ist Datei, dann `TUTOR_HINT_POLICY_JSON`, danach einzelne
`TUTOR_LEVEL_<N>_*`-Felder. `HintPolicy(path=...)` waehlt explizit die Basisdatei,
wendet aber dieselben Umgebungs-Overrides an. `HINT_LEVELS_PATH` darf absolut
sein; relative Werte beziehen sich auf `BASE_DIR` (`code/`), nicht den CWD.

`TUTOR_HINT_POLICY_JSON` ist leer oder ein JSON-Objekt mit vollstaendigen oder
partiellen Objekten fuer bereits vorhandene Stufen, zum Beispiel:

```dotenv
HINT_LEVELS_PATH=config/hint_levels.json
TUTOR_HINT_POLICY_JSON='{"1":{"goal":"Ein Konzept aktivieren.","max_words":60}}'
TUTOR_LEVEL_1_MAX_WORDS=50
TUTOR_LEVEL_1_MAY_INCLUDE='["eine kurze Frage", "ein relevanter Begriff"]'
```

| Feldsuffix nach `TUTOR_LEVEL_<N>_` | Format |
|---|---|
| `NAME`, `GOAL` | Woertlicher Text, nichtleer |
| `MAX_WORDS` | JSON-Ganzzahl, positiv |
| `MAX_SOLUTION_STEPS` | JSON-Ganzzahl >=0 oder `null` |
| `INCLUDE_SOLUTION_STEPS`, `INCLUDE_FINAL_ANSWER` | Booleanwerte wie `1/0`, `true/false`, `yes/no`, `on/off` |
| `MAY_INCLUDE`, `MUST_NOT_INCLUDE` | Bevorzugt JSON-Liste; alternativ Komma/Semikolon; leere Liste erlaubt |

Unbekannte Variablen unter `TUTOR_LEVEL_`, unbekannte Stufen, fehlerhaftes JSON
und falsche Feldtypen brechen ab. Texte bleiben Daten: keine Python-Auswertung,
keine Interpolation von Aufgaben- oder Studierendenfeldern in Policytemplates.

## Umgebungsreferenz

Booleanwerte akzeptieren `1/0`, `true/false`, `yes/no`, `on/off`, ohne
Gross-/Kleinschreibung. Numerische Grenzen und unbekannte Moduswerte werden
beim Laden geprueft. Deploymentaenderungen brauchen eine neue Serverinstanz
oder einen Neustart und fuer Vergleiche eine neue Lauf-/Bedingungsidentitaet.
Die Hauptanwendung haelt ihre aktive Policy in `app.state.hint_policy`.
Health und Config-/Judge-Routen lesen denselben geladenen Policystand;
Dateiaenderungen oder spaetere Envwerte erzeugen keinen Config-GET-Hot-Reload.

### Generierung

| Variable | Default | Vertrag |
|---|---|---|
| `LLM_API_MODE` | `saia` | Backend; `ollama` als lokaler Fallback, Factory akzeptiert auch OpenAI-kompatible Aliasse |
| `LLM_BASE_URL` | `https://chat-ai.academiccloud.de/v1` | Upstream-URL, nicht Teil des Public-Snapshots |
| `LLM_API_KEY` | leer | Lokales Providersecret; niemals in Artefakten |
| `LLM_MODEL` | `qwen3.8-27b` | Generator-Defaultalias; immer auch in der Allowlist |
| `LLM_ALLOWED_MODELS` | eingebaute Auswahl | Kommagetrennte Allowlist; kein beliebiger Requestalias |
| `LLM_TEMPERATURE` | `0.2` | Endlich, `0..2` |
| `LLM_MAX_TOKENS` | `400` | Ganzzahl, `1..32768` |
| `LLM_TIMEOUT` | `180` | Positive Ganzzahl, Sekunden pro Providerrequest |
| `LLM_RETRY_DELAY` | `2` | Endlich, >=0 Sekunden vor SAIA-Fallback |
| `LLM_DISABLE_THINKING` | `1` | SAIA-Unterdrueckung bzw. Ollama `think=not LLM_DISABLE_THINKING`; kein Nachweis effektiver Modellinternas |

### Tutorregeln

| Variable | Default | Vertrag |
|---|---|---|
| `TUTOR_RULES_ID` | `default-policy` | Nichtleeres Bedingungslabel, kein Ersatz fuer den Hash |
| `MAX_HINT_LEVEL` | `4` | Ganzzahl `0..32`; Policy muss `0..MAX_HINT_LEVEL` enthalten |
| `TUTOR_START_LEVEL` | `1` | Baseline `DEFAULT_HINT_LEVEL`, innerhalb `0..MAX_HINT_LEVEL` |
| `TUTOR_START_MODE` | `fixed` | `fixed` oder `individual`; explizite Startstufe hat Vorrang |
| `TUTOR_DIAGNOSIS_MODE` | `provided` | `provided`, `model` oder `none` |
| `TUTOR_POLICY_MODE` | `tutor` | `tutor` oder `general` |
| `TUTOR_RESPONSE_FORMAT` | `text` | `text` oder `structured` |
| `TUTOR_ASK_ACTIVATING_QUESTION` | `1` | Aktivierende Rueckfrage als allgemeine Tutorregel |
| `TUTOR_HIDE_HINT_LEVEL` | `1` | Verbot interner Stufennennung im Tutoroutput; nicht der HTML-Debugschalter |
| `TUTOR_ENFORCE_WORD_LIMIT` | `1` | Wortlimit im Tutorprompt und dessen Evaluationscheck aktiv; kein Produktionsfilter |
| `TUTOR_LATEX_NOTATION` | `1` | LaTeX-Notationsregel im Tutorprompt (inline `\( \)`, abgesetzt `$$ $$`) fuer die KaTeX-Anzeige; keine Outputfilterung oder Notationskonvertierung |
| `HINT_LEVELS_PATH` | `config/hint_levels.json` | Basisdatei, relativ zu `code/` oder absolut |
| `TUTOR_HINT_POLICY_JSON` | leer | Partieller/voller Datenoverride bestehender Stufen |

`provided` nutzt bereitgestellte Diagnosen mit ihrer Unsicherheit; synthetische
Fehlerszenarien sind keine PRT-Nachweise. `model` blendet Diagnosecode und
Feedback aus dem effektiven Prompt aus und erlaubt eigenstaendige Fehleranalyse
als kurze unsichere Hypothese. `none` blendet beide Felder aus und fordert keine
Diagnose. `provided` und `none` verbieten eigenstaendige Neubewertung;
tatsaechlich bereitgestellte autoritative Evidenz bleibt in allen Modi
verbindlich. Die Scoreoption wird durch diese Moduswahl nicht entfernt.

`structured` verlangt genau `{"hint":"...","diagnosis_hypothesis":null}`;
die Hypothese darf nur in `model` ein String sein. Der Server validiert das
Objekt, speichert `hint` als Assistantnachricht und gibt die Hypothese separat
zurueck. Er erfindet kein Diagnosefeld aus freiem Text.

### Kontext und Grenzen

| Variable | Default | Vertrag |
|---|---|---|
| `CONTEXT_OPTIONS` | `question_text,student_answer,diagnosis_code,prt_feedback,learning_goals,solution_steps,final_answer,chat_history` | Defaultflags fuer HTML und `ContextOptions` |
| `TUTOR_STAGE0_CONTEXT_OPTIONS` | `question_text,student_answer,learning_goals,math_rules,chat_history` | Unabhaengige Obergrenze nur auf Stufe 0 |
| `MAX_STUDENT_ANSWER_LENGTH` | `2000` | Laengenlimit fuer die urspruengliche Antwort |
| `MAX_QUESTION_TEXT_LENGTH` | `5000` | Moodle-Volltext/Funktion; gespeicherter JSON-Kontext mindestens bis 10000 Zeichen erlaubt |
| `MAX_CHAT_MESSAGE_LENGTH` | `2000` | Folgefrage/Formularlimit |
| `MAX_HISTORY_MESSAGES` | `12` | Letzte gespeicherte Nachrichten fuer Generierung |
| `DATABASE_PATH` | `code/data/tutor.db` als absoluter Default | Relative Overrides beziehen sich auf den Prozess-CWD |
| `DEBUG_MODE` | `1` | HTML-Diagnosebox, Stufenauswahl und Prompt-/Optionsdebugger; keine JSON-Debugsperre |

Listen akzeptieren Komma oder Semikolon und Kontextnamen mit/ohne `include_`.
Gueltig sind die zehn Namen aus `ContextOptions`: `question_text`,
`student_answer`, `diagnosis_code`, `prt_feedback`, `score`, `learning_goals`,
`math_rules`, `solution_steps`, `final_answer`, `chat_history`.
Unbekannte Namen verhindern den Start; eine leere Liste deaktiviert alle Flags.

`effective_context_options(options, level)` verknuepft auf Stufe 0 angeforderte
Flags mit der Stage-0-Obergrenze und entfernt in `model|none` Diagnose/Feedback.
Es aktiviert nie ein zuvor abgewaehltes Feld. Die aktuelle Chatfrage wird auch
bei ausgeschalteter Historie uebermittelt, ohne den alten Verlauf zu aktivieren.
Das gilt auch, wenn Historie erst durch den Stage-0-Cap ausgeschaltet wird.
Die Stage-0-Frage bleibt im Tutormodus das Stufenziel, auch wenn die allgemeine
aktivierende Rueckfrage ausgeschaltet ist. Ein Override der Erlaubnisliste
ist ein separat dokumentierter Policybestandteil, kein unsichtbarer Flagschalter.

### Adaption

| Variable | Default | Vertrag |
|---|---|---|
| `TUTOR_ADAPTIVE_ENABLED` | `0` | Keine automatische Erhoehung im Default |
| `TUTOR_ADAPTIVE_AFTER_SECONDS` | `120` | Endliche nichtnegative Schwelle |
| `TUTOR_ADAPTIVE_STEP` | `1` | Positive Ganzzahl |
| `TUTOR_ADAPTIVE_MAX_LEVEL` | `MAX_HINT_LEVEL` | Obergrenze innerhalb des aktiven Stufenbereichs |
| `TUTOR_ADAPTIVE_CONFUSION_PHRASES` | `ich verstehe nicht,keine ahnung,ich weiss nicht,no idea` | Komma/Semikolon; normalisierte Selbstbericht-Phrasen, leere Liste erlaubt |

Entscheidung erst bei der naechsten Nachricht: Schwelle seit letzter
erfolgreicher Antwort **und** erkannter Selbstbericht muessen vorliegen.
Zeit allein ist kein Verstaendnisnachweis. Kein Timer, Polling oder neuer
LLM-Aufruf nach blossen 120 Sekunden. Erfolg schreibt Zielstufe und
Entscheidungsmetadaten; bei Fehler bleibt die gespeicherte Stufe unveraendert.
Explizite Stufenwahl hat Vorrang, keine Rueckstufung. Die persistierte Baseline
bleibt unabhaengig von spaeteren Erhoehungen erhalten.

Normale Intervalle nutzen nur die monotone Uhr desselben Prozesses mit
`SESSION_CLOCK_ID` als UUID. Neustart/anderer Worker bedeutet unbekanntes
Intervall (`null`, bei aktivem Verwirrungssignal `time_unknown`), nicht aus
Wallclock rekonstruierte Lernzeit. Kein aktives Bearbeitungszeittracking.
Geschuetzte Simulationswerte gelten requestweise, ohne sticky Zeitquelle;
Details in [../app/README.md](../app/README.md).

### Evaluation und Judge

| Variable | Default | Vertrag |
|---|---|---|
| `EVALUATION_API_ENABLED` | `0` | Geschuetzte Routen deaktiviert (`404`) |
| `EVALUATION_API_TOKEN` | leer | Serversecret; aktiviert ohne nichtleeren Token bedeutet Startfehler |
| `EVALUATION_JUDGE_MODEL` | leer | Expliziter erlaubter Alias erforderlich, bevor der Judge benutzt wird |
| `EVALUATION_JUDGE_TEMPERATURE` | `0.0` | Endlich, `0..2` |
| `EVALUATION_JUDGE_MAX_TOKENS` | `1200` | Ganzzahl, `1..32768` |
| `TUTOR_EVALUATION_TOKEN` | kein Serverdefault | Clientumgebung fuer Header `X-Evaluation-Token`, muss zum Serversecret passen |

`GET /api/evaluation/config` ist ein authentifizierter Snapshot ohne
Provideraufruf; `POST /api/evaluation/judge` generiert nur nach explizitem
Request. Das Clientwerkzeug verlangt einen anderen Judgealias als den
gespeicherten Generatoralias. Token ist kein Providerkey. Normale Tutor-Routen
und JSON-Debugfelder werden hierdurch nicht authentifiziert.

## Oeffentliche Identitaet

`public_configuration(policy)` liefert `schema_version="tutor-config-1"`,
aktive `hint_policy`, `generation`, `tutor_rules` (mit `rules_id`), `start`,
`adaptation`, `limits` (einschliesslich Historienlimit), `context_defaults`
und `stage0_context_options`. Kontextdicts
verwenden alle zehn `include_*`-Namen; die Defaults bleiben fuer spaetere Stufen
beobachtbar, auch wenn Startstufe 0 sie temporaer kappt.

`configuration_hash(configuration)` bildet SHA-256 ueber kanonisches ASCII-JSON
mit sortierten Keys und ohne nichtendliche Zahlen. Keine Keys, Token,
Upstream-URL, Datenbankpfade oder Modell-Allowlist im Snapshot. `/health` und
Generierungsantworten melden `config_sha256`; der geschuetzte Config-Endpunkt
liefert zusaetzlich Judge-Regel-ID, Alias und Parameter. Diese Judgeidentitaet
wird separat gepinnt und ist kein Teil der Tutor-Konfigurationshashes.

### Migration und Grenzen

Eigene alte Policies explizit um Stufe `"0"` mit allen acht Feldern erweitern;
Default: Diagnosephase, `max_words=70`, keine Schritte/Endloesung,
`max_solution_steps=0`. Alte Policies ohne `max_solution_steps` brauchen auch
dieses Pflichtfeld: `0`, `0`, `3`, `null` fuer Stufen 1 bis 4. Fehlende Felder
oder Stufe 0 werden nicht automatisch ergaenzt. Ein reiner Level-0-Betrieb mit
`MAX_HINT_LEVEL=0` braucht explizit `TUTOR_START_LEVEL=0`.

Die Legacyfelder `tutor_policy`, `hint_levels`, `prompt_context_policy` in Tasks
bleiben schemapflichtig, steuern aber nicht den generischen Prompt. Die
additive SQLite-Migration ist separat in [../data/README.md](../data/README.md)
dokumentiert; sie darf keine historischen Startentscheidungen erfinden.

Vorher wurden auf Stufe 3 alle Lösungsschritte übertragen, einschließlich eines
Schritts mit dem Endergebnis. Das konnte die Endlösung trotz ausgeschaltetem
`include_final_answer` offenlegen. Jetzt gilt zusätzlich das zentrale Mengenlimit.
Wenn die Endlösung nicht durch **beide** Freigaben erlaubt ist, endet die Liste
vor dem ersten Schritt, der die konkrete `final_answer`-Zeichenfolge enthält.

Dies ist keine symbolische Aequivalenzpruefung. Anders geschriebene Loesungen in
Schritten/Verlauf und vollstaendige Modelloutputs werden nicht zuverlaessig
erkannt. Referenzschritte weiterhin passend ordnen und pruefen; synthetische
Referenzen nicht als verifiziert deklarieren. Outputpruefung per STACK/Maxima
bleibt ein separater Arbeitspunkt.
