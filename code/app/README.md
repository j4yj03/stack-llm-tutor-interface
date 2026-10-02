# Paket `code/app/`

Stand: 2026-10-02. FastAPI-Anwendung des KI-Tutors. Entrypoint: `app.main:app`.
Die hier beschriebenen Defaults sind nicht automatisch die Einstellungen einer
laufenden Instanz. Vollstaendige Umgebungsreferenz:
[../config/README.md](../config/README.md); Evaluation:
[../evaluation/README.md](../evaluation/README.md).

## Datenfluss

```text
Moodle/STACK -> GET /start -> main.py
    -> task_loader / geladene validierte Tasks
    -> Startentscheidung: explizit, fixed oder extra LLM-Auswahl
    -> ChatStore: UUID, persistierter Kontext, Baseline und Sessionzustand
    -> HintPolicy + effektive Kontextflags
    -> PromptBuilder: ein gemeinsamer Promptpfad
    -> app.llm: SAIA/Ollama, explizite Generatorparameter
    -> Erfolgscommit: Stufe, Assistantnachricht und Zustand
    -> tutor_page.html / JSON-Antwort mit beobachteten Metadaten
```

## Dateien

| Datei | Verantwortung |
|---|---|
| `main.py` | Tutor-Routen, Kontextidentitaet, Startwahl, Generierung, Erfolgscommit und Responsemetadaten; bindet den Evaluationrouter ein |
| `config.py` | Pfade, `LLM_*`, `TUTOR_*`, `EVALUATION_*`, Allowlist und validierte Grenzen |
| `runtime_config.py` | `effective_context_options`, `public_configuration`, `configuration_hash`; keine Provider- oder DB-Zugriffe |
| `adaptation.py` | `decide_hint_level`; reine, konfigurierte Entscheidung aus Intervall und Selbstbericht bei Folgeinteraktionen |
| `evaluation_api.py` | Opt-in-Router fuer authentifizierten Config-Snapshot und strukturierten Zweitmodellreview |
| `schemas.py` | Pydantic-Modelle: `ContextOptions`, `StackContext`, `TutorRequest`, `NextHintRequest`, `UserChatRequest`, `ChatMessage`, `TutorResponse`, `ChatHistoryResponse` |
| `database.py` | Initialisierung mit Foreign Keys und additiver Baseline-/Sessionzustandsmigration |
| `chat_store.py` | UUID-Chats, Nachrichten, aktuelle Stufe, persistierte Baseline und Sessionzustand; Bereich `0..MAX_HINT_LEVEL` |
| `hint_policy.py` | Konfigurierte Datei, JSON- und per-Level-Overrides; alle aktiven Stufen `0..MAX_HINT_LEVEL` vollstaendig und typgeprueft |
| `prompt_builder.py` | System-Nachricht (Tutorrolle, Stufenregeln, Prompt-Injection-Schutz) + Kontext-Abschnitte je nach `ContextOptions`; Doppelprüfung bei `solution_steps`/`final_answer` (Option **und** Stufe) |
| `math_notation.py` | Anzeige-Konvertierung reiner STACK-/Maxima-Ausdrücke nach LaTeX (stdlib-AST-Whitelist, kein eval, Fallback None); ändert keinerlei gespeicherte Kontexte oder Prompts |
| `task_loader.py` | Lädt `tasks/*.json`, validiert gegen JSON-Schema (Draft 2020-12), erzwingt eindeutige `question_id`s; Fail-fast bei ungültigen Dateien |
| `ollama_client.py` | Kompatibilitäts-Wrapper (`call_ollama_chat` u. a. delegieren an `app.llm.create_llm_client`) |

## Endpunkte

| Route | Methode | Zweck |
|---|---|---|
| `/health` | GET | Aufgabenanzahl, Defaultalias, `config_sha256`, `rules_id`; kein Provideraufruf |
| `/tasks` | GET | Liste der verfügbaren Aufgaben |
| `/start` | GET | Moodle/STACK-Adapter (HTML-Seite) |
| `/tutor/{chat_id}/message` | POST | Formular-Rückfrage; rendert Chat und Debug-Prompt ohne JavaScript |
| `/tutor/{chat_id}/retry` | POST | Generierung auf Versuchsstufe ohne erneute Speicherung der Nutzerfrage |
| `/api/tutor/start` | POST | Neuer Chat oder Fortsetzung mit identischem bereitgestelltem `StackContext` |
| `/api/tutor/{chat_id}/next-hint` | POST | Aktuelle Stufe +1, gekappt durch `MAX_HINT_LEVEL`; Commit erst bei Erfolg |
| `/api/tutor/{chat_id}/message` | POST | Folgefrage; optional explizite oder adaptive Zielstufe |
| `/api/tutor/{chat_id}/history` | GET | Chatverlauf abrufen |
| `/api/evaluation/config` | GET | Geschuetzter oeffentlicher Konfigurations-/Judge-Snapshot, kein LLM-Aufruf |
| `/api/evaluation/judge` | POST | Geschuetzter strukturierter Modellreview einer gespeicherten Tutorantwort |

## Start und Regeln

Gueltige Stufen sind `0..MAX_HINT_LEVEL`; `MAX_HINT_LEVEL` erlaubt `0..32`,
Defaultmaximum `4`. Bei Maximum 0 ist explizit `TUTOR_START_LEVEL=0` noetig.
`TUTOR_START_LEVEL=1` bestimmt `DEFAULT_HINT_LEVEL`. Fuer einen neuen Chat
entscheidet eine explizite Stufe zuerst; fehlt sie (`null`/ausgelassen), gilt:

- `fixed`: konfigurierte Startbaseline, eine Operation fuer die Antwort.
- `individual`: erst eine separate LLM-Auswahl von `hint_level` und `reason`,
  dann Generierung auf der gewaehlten Stufe. Bei Fehler kein stiller Fallback.
  Die Auswahl ist eine unsichere Unterstuetzungsentscheidung, kein Grading.

Der API-Auswahlprompt nutzt die `context_options` des Requests, verknuepft mit
Stage-0-Obergrenze und Diagnosefilter; HTML nutzt seine konfigurierten Defaults.
Die Kappung aktiviert keine abgewaehlten Felder. Auswahl- und Hinweisnachrichten werden
getrennt als `start_prompt_messages` und `prompt_messages` beobachtbar.
Bei bestehenden Chats ohne explizite Stufe gilt die gespeicherte Stufe;
die Startwahl wird nicht wiederholt. `baseline_hint_level` speichert die
initial gewaehlte Stufe und wird durch spaetere Erhoehungen nicht ersetzt.

Stufe 0 (`stage="diagnostic"`) fordert im Tutormodus eine kurze diagnostische
Frage zum Verstaendnis/Vorgehen. `TUTOR_STAGE0_CONTEXT_OPTIONS` begrenzt die
angeforderten zehn Flags, aktiviert keines. Die Defaultobergrenze erlaubt
Frage, Antwort, Lernziele, Regeln und Historie; nur angeforderte Felder werden
sichtbar. Diagnose/Feedback/Score/Referenzschritte/-endloesung sind
nicht freigegeben. Auf positiven Stufen gilt `stage="hint"`.

| Modus | Promptvertrag |
|---|---|
| `TUTOR_DIAGNOSIS_MODE=provided` | Bereitgestellter Fehlerkontext mit Herkunft/Unsicherheit; keine erfundene Diagnose oder eigenstaendige Neubewertung |
| `TUTOR_DIAGNOSIS_MODE=model` | Code/Feedback nicht im effektiven Prompt; eigenstaendige Fehleranalyse der sichtbaren Aufgabe/Antwort, hoechstens eine unsichere Hypothese |
| `TUTOR_DIAGNOSIS_MODE=none` | Code/Feedback entfernt; keine Diagnose/Hypothese und keine eigenstaendige Neubewertung |
| `TUTOR_POLICY_MODE=tutor` | Tutorrolle, aktive Stufe, Ziele und Erlaubnis-/Verbotslisten sowie aktivierte Zusatzregeln |
| `TUTOR_POLICY_MODE=general` | Allgemeiner Assistent ohne didaktische Rolle/Stufenregeln; Diagnosemodus bleibt konfiguriert |

`StackContext.diagnosis_source` ist optional: `synthetic`, `provided`, `prt`,
`stack`, `stack_prt`, `unknown` oder `null`. Ohne autoritative Herkunft heissen
die Promptabschnitte `BEREITGESTELLTE DIAGNOSE`/`BEREITGESTELLTES FEEDBACK`, nicht
PRT-Befund. `/start` markiert den URL-/Task-Kontext als `provided`; ein
editierbarer Moodle-Link beweist kein Grading. Scoreflags bleiben unveraendert.
Tatsaechlich bereitgestellte verifizierte STACK-/PRT-Ergebnisse duerfen in
keinem Modus ueberschrieben werden; blosse Herkunftslabels verifizieren nichts.

`TUTOR_ASK_ACTIVATING_QUESTION`, `TUTOR_HIDE_HINT_LEVEL`,
`TUTOR_ENFORCE_WORD_LIMIT` und `TUTOR_LATEX_NOTATION` steuern Zusatzregeln, alle
standardmaessig `true`. Die LaTeX-Regel fordert Formeln als `\( \)`/`$$ $$` an,
damit die Tutorseite sie mit KaTeX rendert; CAS-Syntax in Aufgabe und Antwort
wird nicht umgewandelt. Im General-Modus sind diese Tutorregeln inaktiv; die
Sicherheitsregeln und Referenz-Doppelfreigaben gelten weiter. Wortlimits sind
Promptanweisungen, keine Trunkierung oder vollstaendige Outputfilter.

`TUTOR_RESPONSE_FORMAT=structured` verlangt genau ein JSON-Objekt mit
`hint: string` und `diagnosis_hypothesis: string|null`. Eine nichtleere
Hintausgabe ist erforderlich; nur `model` erlaubt eine Stringhypothese.
Falsche Struktur liefert HTTP 502. Im Default `text` gibt es keine automatische
Extraktion einer Hypothese. Als Assistantnachricht wird nur der Hint gespeichert.

## Kontext und Chat

`GET /start` akzeptiert weiterhin `qid`, `diagnosis`, `ans1`, `hint_level`,
`model`, `chat_id` sowie optional Aufgaben-Kontext in zwei Varianten:

- `funktion`: die konkret instanziierte Funktion aus STACK (z. B.
  `f(x)=3*%e^(x^2-2*%e^x)`). Das Backend setzt sie in den generischen
  Textbaustein `question_text_template` der Aufgabe ein (Platzhalter
  `{funktion}`, vom Loader geprüft).
- `question_text`: vollständiger Aufgabentext als Vollüberschreibung.

Beide Parameter sind gegenseitig exklusiv (HTTP 400 bei beiden), werden auf
Länge (`MAX_QUESTION_TEXT_LENGTH`, Default 5000) und Leere geprüft. Der
bestehende JSON-API-/Speicherkontext darf bis zu `MAX_CONTEXT_QUESTION_TEXT`
(Standard 10000) Zeichen enthalten; URL-Limits verkürzen keine bereits
gespeicherten Chats. Ohne beide Parameter gilt der generische Aufgabentext
der JSON (Anweisung ohne konkrete Funktion; für API- und Tests nutzbar).

Bei abweichendem Aufgabentext (Volltext oder Komposition) hängt
`task_to_stack_context` die **generischen** Aufgabendaten an: Lernziele,
mathematische Regeln und den Diagnosetitel — die Aufgaben-JSON enthält dafür
keine festen Zufallswerte mehr (per Test erzwungen; `question_text` und
`given_data` sind generisch, die konkrete Funktion stammt stets aus
Moodle/STACK). Die lokale Beispiel-Musterlösung (`model_solution`) ist
Demodaten eines festen Beispiels und wird bei Varianten nie angehängt, auch
nicht auf Stufe 4; Lösungsschritte und Endlösung bleiben leer. Die
HTML-Flows aktivieren `include_learning_goals` im Default; eine angepasste
`CONTEXT_OPTIONS`-Auswahl kann sie abwaehlen. Die Aufgaben-JSON liefert den
Katalog der erlaubten Diagnosen.

Fuer die Anzeige auf der Tutorseite konvertiert `math_notation.py` reine
STACK-/Maxima-Ausdruecke nach LaTeX: die komponierte `{funktion}` im
Aufgabenblock, eine reine Ausdrucksantwort unter „Deine Antwort" und
Folgenachrichten im Chat, deren gesamter Text ein Ausdruck ist. Nicht
erkennbare Eingaben (Prosa, unbekannte Syntax) bleiben roh bzw. im
`<code>`-Element. Die Konvertierung ist ausschliesslich Anzeige: gespeicherter
Kontext, Prompt und JSON-Antworten enthalten weiterhin die CAS-Syntax.

Bei bestehendem `chat_id` muss die Kombination aus Aufgabe (Volltext oder
komponierter Text), Antwort und Diagnose zum gespeicherten Kontext passen.
HTML-bedingte LF/CRLF-Unterschiede der Antwort sind erlaubt. Geänderte
Aufgaben/Antworten brauchen einen neuen Link ohne `chat_id`. Nicht erneut
übergebene `question_text`/`funktion` werden aus dem Chat geladen. Niedrigere
Hilfestufen bestehender Chats werden abgewiesen, damit ein alter Stufe-4-Verlauf
nicht als Stufe-1-Kontext verwendet wird.

`POST /tutor/{chat_id}/retry` wiederholt eine Generierung auf der Versuchsstufe:
Die gespeicherte Nutzerfrage wird **nicht** erneut eingetragen;
bei Erfolg landet nur die neue Assistant-Antwort im Verlauf und die
Ziel-Hilfestufe wird gesetzt. Das Formfeld `hint_level` (optional) bestimmt
die Zielstufe — nie niedriger als die gespeicherte Stufe, sonst HTTP 400;
ein fehlgeschlagener Stufenaufstieg wird also auf der Versuchsstufe
wiederholt. Das Formular erscheint inline **neben der unbeantworteten
Frage** in der Chatblase; existiert keine Chatfrage (typischer
`/start`-Fehler), steht es in der Fehlerbox. Solange eine Frage unbeantwortet
ist (Retry inline), ist der Senden-Knopf des Chat-Formulars deaktiviert —
der Server akzeptiert Nachrichten weiterhin, die Sperre ist clientseitig.
Ein Retry kann Provideraufrufe verbrauchen. Der Endpoint verifiziert keinen
dauerhaften Fehlerstatus und konsumiert kein Token; erneutes manuelles POSTen
kann weitere Antworten erzeugen. Er ist nicht idempotent.

`POST /tutor/{chat_id}/message` nimmt `message` und optional `model` als
`application/x-www-form-urlencoded` entgegen (`python-multipart` erforderlich).
Nachrichtenlimit: `MAX_CHAT_MESSAGE_LENGTH`, standardmäßig 2000 Zeichen.
Leere/zu lange Nachrichten werden vor Speicherung mit einer HTML-Fehlermeldung
abgewiesen. Bei LLM-Fehlern bleibt die bereits gespeicherte Frage im Verlauf;
HTTP 429/502 liefern weiterhin eine nutzbare HTML-Seite mit sicherem Fehlertext
und dem Prompt des Versuchs. Folgehints erhöhen die Stufe erst nach erfolgreicher
Generierung. Ein Browser-Neuladen nach einem POST kann erneut senden; es gibt
noch keine idempotenten Requests oder ein Post/Redirect/Get-Archiv.

Der JSON-Start mit vorhandener `chat_id` vergleicht den normalisierten
Pydantic-`StackContext` vollstaendig mit dem gespeicherten Kontext. Aenderungen
werden mit HTTP 400 abgewiesen; eine neue Antwort/Variante braucht einen neuen
Chat. Das prueft Identitaet, nicht mathematische Gueltigkeit gegen STACK.

Ist die **effektive** Historie ausgeschaltet, wird die aktuelle gespeicherte
Nutzerfrage trotzdem ueber `current_message` aufgenommen, auch wenn erst der
Stage-0-Cap das angeforderte Historienflag entfernt. Mit Historie bleibt
sie im normalen User-Verlauf; der Server dupliziert sie nicht. Historie ist
optionaler Kontext, keine Voraussetzung dafuer, die aktuelle Anfrage zu sehen.

## Folgeadaption

Standard: `TUTOR_ADAPTIVE_ENABLED=0`; normale Fragen bleiben auf derselben
Stufe. Eingeschaltet prueft der Server erst beim naechsten HTML-/JSON-POST
das Intervall seit der letzten erfolgreichen Antwort und einen Selbstbericht
aus `TUTOR_ADAPTIVE_CONFUSION_PHRASES`. Defaultschwelle 120 Sekunden, Schritt 1,
Obergrenze `TUTOR_ADAPTIVE_MAX_LEVEL` (Default `MAX_HINT_LEVEL`). Beide Signale
sind erforderlich; Zeit allein fuehrt nicht zur Erhoehung.

Das normale Intervall nutzt `time.monotonic()` und die Prozess-UUID
`SESSION_CLOCK_ID`. Nach Neustart oder Wechsel zu einem anderen Worker ist
`elapsed_seconds=null`; bei aktivierter Adaption mit Verwirrungssignal lautet
der Grund `time_unknown`. Kein Rueckrechnen aus `last_response_at` oder anderer
Wallclockzeit, kein Tracking aktiver Bearbeitungszeit.

Kein Hintergrundtimer und keine proaktive Generierung. Das Serverintervall ist
keine gemessene Lernzeit. Erfolg setzt Stufe, Antwortzeit und Entscheidungsdaten;
Fehler laesst die Stufe unveraendert und bewahrt die Nutzerfrage. Explizite
JSON-`hint_level`-Wahl hat Vorrang und darf nicht sinken. `/next-hint` bleibt
ein separater manueller +1-Aufstieg, keine Anwendung der adaptiven Schrittweite.

JSON-Folgefragen koennen `simulation_elapsed_seconds` (endlich, `0..86400`)
und `confusion_signal` enthalten. Diese Ausnahmeeingaben brauchen die
Evaluationauthentifizierung; sie werden als `time_source="simulated"` bzw.
`signal_source="scripted"` markiert und loesen keinen Sleep aus. Gewoehnliche
Signale heissen `observed_server_interval`/`self_report_phrase`.
Simulation gilt nur fuer den expliziten Request; ein spaeterer normaler Request
erbt weder den simulierten Zeitwert noch dessen `time_source`.

## LLM-Fehlerverhalten

Der SAIA-Client versucht jeden Chat-Aufruf einmal; schlägt er mit einem
Verbindungs-/HTTP-5xx-Fehler fehl und enthält der Request das vLLM-spezifische
Feld `chat_template_kwargs`, wird **einmal** ohne dieses Feld wiederholt
(Wartezeit: `LLM_RETRY_DELAY`, Standard 2 Sekunden). Hintergrund: Manche
Gateways antworten auf das Feld mit HTTP 500 und leerem Body (siehe
AGENTS.md, Known Issue 8). Steht `LLM_DISABLE_THINKING=0`, entfällt das Feld
von vornherein und es gibt keinen Fallback-Versuch.

Das gilt auch fuer individuelle Startauswahl und Judgeoperationen; Auswahlfehler
haben ein eigenes HTTP-Fehlermapping, keinen stillen Baselinefallback.

Sowohl `main.py` (Rate-Limit, generische LLM-Fehler) als auch der SAIA-Client
(Fallback-Fälle) loggen die Ursache serverseitig mit (`logger.warning`,
inklusive HTTP-Status und Antwortauszug der Plattform, ohne Keys oder
Auth-Header). Studierende sehen weiterhin nur die allgemeine Fehlermeldung
sowie den versuchten Prompt. Bleiben 5xx-Fehler bestehen, SAIA-Dashboard
prüfen, `LLM_MODEL` wechseln oder `LLM_DISABLE_THINKING=0` setzen.

## Debug-Prompt

`generate_hint` gibt `(tutor_answer, messages, diagnosis_hypothesis)` zurueck.
Der Hinweis-Prompt wird nur einmal
aufgebaut und vor dem Speichern der neuen Tutorantwort angezeigt, nicht aus dem
späteren Verlauf rekonstruiert. `HintGenerationError` trägt die Nachrichten eines
fehlgeschlagenen Versuchs für die HTML-Anzeige, ohne Upstream-Fehlerkörper
weiterzureichen. `render_tutor_page` liest Anzeige und Verlauf aus demselben Chat.

Die JSON-Generierungsantworten enthalten neben Hint, Chat-/Task-/Modellidentitaet
und Verlauf folgende Metadaten; History-Endpunkte behalten ihr bisheriges Format:

| Feld | Bedeutung |
|---|---|
| `prompt_messages` | Tatsaechliche Nachrichten der Hinweisgenerierung, keine Rekonstruktion nach Speicherung |
| `requested_context_options`, `context_options` | Angeforderte versus effektive Flags nach Stage-0-/Diagnosefilter |
| `baseline_hint_level` | Initiale Stufe des Chats, unabhaengig von aktueller Stufe |
| `start_decision`, `start_prompt_messages` | Quelle, Auswahlgrund, Stufe, Hash und gegebenenfalls echte Auswahlmessages |
| `adaptation` | Letzte gespeicherte Folgeentscheidung mit vorheriger/Zielstufe, Signalen, Zeitquelle, Grund und `applied` |
| `hint_policy` | Vollstaendiger effektiver Policyeintrag der generierten Stufe; im General-Modus keine aktive Output-Tutorregel |
| `configuration`, `config_sha256` | Oeffentlicher Snapshot `tutor-config-1` und kanonischer SHA-256 |
| `policy_mode`, `stage`, `diagnosis_hypothesis` | Regelmodus, diagnostische/Hintphase und optional getrennte Modellhypothese |
| `llm_operations` | Logische LLM-Operationen dieses Aufrufs, bei individueller Erstwahl typischerweise 2; nicht Upstreamversuche oder Tokenusage |

`start_decision.source` ist `configured`, `explicit` oder `model_hypothesis`.
Es enthaelt `mode`, `selected_level`, `reason`, `configuration_sha256`,
optionale `prompt_messages`/effektive Auswahl-`context_options` und die Anzahl
reiner Auswahloperationen (0/1).
Das separate Responsefeld `llm_operations` zaehlt Auswahl plus Hint des Aufrufs.
`adaptation` beschreibt die erfolgreich gespeicherte Folgeentscheidung;
Generierungen ohne solche Entscheidung, etwa manuelle Folgehints/Retry,
setzen das Feld auf `{}`, statt einen alten Entscheidungsgrund weiterzutragen.

Snapshots enthalten aktive Levels, Generation, Tutorregeln inklusive `rules_id`,
Start, Adaption, Historien-/Laengenlimits, Kontextdefaults und Stage-0-Obergrenze.
Aenderungen am Historienlimit aendern ebenfalls den Konfigurationshash. Keine Secrets,
Upstream-URL oder Allowlist. Nicht beobachtete Provider-IDs, Modelldigest,
Tokenusage, Finishreason, Upstreamversuche und effektiver Thinking-Modus
bleiben unbekannt. Debugdaten sind kein dauerhaftes Server-Requestarchiv.

Die aktive `HintPolicy` liegt in `app.state.hint_policy`; Health, Generierung
und geschuetzter Config-/Judge-Snapshot verwenden dieselbe Instanz. Kein
Datei-Hot-Reload durch einen Config-GET. Umgebungs-/Policyaenderungen werden
beim Prozessstart geladen und brauchen einen Neustart, fuer Vergleiche neue Runs.

Liegt die gespeicherte Stufe eines alten Chats oberhalb einer abgesenkten
aktiven Obergrenze, wird die Fortsetzung vor Generierung mit HTTP 409 abgewiesen.
Keine stille Rueckstufung; fuer die neue Policy einen neuen Chat verwenden.
Nicht UTF-8-kodierbare Modelltexte werden vor einer Stufen-/Antwortpersistenz
als sichere Antwortfehler behandelt.

Der HTML-Debug-Block (einklappbares `<details>` „Debug-Informationen“) zeigt
den Hinweis-Prompt und Optionsdaten, nicht alle obigen JSON-Metadaten.
Auf erfolgreichen und fehlgeschlagenen Generierungsversuchen sind es effektive
Flags; angeforderte Optionen stehen separat in den JSON-Antworten.
Options-JSON steht unter `debug-context-options`, Prompt-JSON unter
`debug-prompt`; daneben Stufendropdown und die historische Diagnosebox.
Bei fehlender Generierung (z. B. abgewiesene Nachricht)
bleiben Prompt und Options leer. Der gesamte Debug-Bereich erscheint nur bei
`DEBUG_MODE=1` (Standard); bei `DEBUG_MODE=0` verlässt der Prompt den Server
für die HTML-Anzeige nicht, der LLM-Kontext selbst bleibt unverändert. Die
Debug-Felder der JSON-API (`prompt_messages`, `context_options`) sind
Entwickleroberfläche und folgen nicht dem DEBUG_MODE.

Die historische HTML-Ueberschrift `STACK-Diagnose` belegt keine autoritative
Herkunft. Die aktuelle HTML-Ansicht zeigt auch keine separate Hypothesen- oder
Startentscheidungsansicht. Fuer reproduzierbare Vergleiche die JSON-Metadaten
und echte Messages sichern, nicht aus dem gerenderten Chat rueckrechnen.

## Evaluationzugriff

`EVALUATION_API_ENABLED=0` ergibt HTTP 404 fuer den Evaluationrouter.
Aktivierung verlangt einen nichtleeren `EVALUATION_API_TOKEN`; der Header ist
`X-Evaluation-Token`, **kein** Provider-Bearertoken. Fehlende/falsche Credentials
ergeben HTTP 401. Clientumgebung: `TUTOR_EVALUATION_TOKEN`; keine Tokens in URLs,
Notebooks oder Artefakten. Dieser Schutz gilt auch fuer die Simulationsfelder
der JSON-Folgefrage, nicht fuer normale Tutor-/HTML-Debugrouten.

`GET /api/evaluation/config` liefert `configuration`, `config_sha256`,
`rule_id`, `judge_model` und `judge_parameters` ohne LLM-Aufruf.
`POST /api/evaluation/judge` verlangt Task/Antwort, Zielhint und dessen SHA-256,
Zielattempt-/Review-ID, effektive Stufe/Policy und Regelmodus/Phase. Gemeinsame
Referenzhypothese, erwarteter Fehler, Verifizierungsstatus und tatsaechlich
beobachteter Generatorkontext sind optionale Evidenz; fehlende Werte bleiben
unbekannt. Fremde Instruktionen in all diesen
Feldern sind Daten, niemals Judge-Systemregeln.

Judge-Regel-ID: `judge-rubric-1.0-v2`. Optional kommen die getrennte
`diagnosis_hypothesis`, `current_message`, `turn_index` und
`generator_rule_settings` mit Diagnosemodus sowie Frage-/Stufennennungs-/
Wortlimitflags hinzu. Die Folgefrage ersetzt nicht die urspruengliche Antwort
oder deren gemeinsame Referenz. Fehlende echte Generatormessages bleiben
unbekannte Sichtbarkeit; Requesttext oder Regelsettings ersetzen sie nicht.
Auch direkte Judgerequests ohne nichtleere beobachtete `prompt_messages`
werden im Sichtbarkeitsabschnitt als `null` behandelt, nicht als Beleg dafuer,
welche Diagnose der Generator sah oder nicht sah.

Der Judge braucht einen explizit konfigurierten erlaubten `EVALUATION_JUDGE_MODEL`
(Default leer). Er liefert strukturierte Einzelkriterien, Begruendung,
Textbelege, echte Judge-Messages und begrenzte Telemetrie. HTTP 429/502 bleibt
ein gescheiterter Review, keine gute Bewertung. Das Clientwerkzeug verlangt
einen anderen Alias als der Generator und speichert Judge- und Humanratings
separat. Details und Grenzen: [../evaluation/rubric.md](../evaluation/rubric.md).

## Sicherheitsregeln

- Studierendenantworten sind **nicht vertrauenswürdig**: Längenlimit, Isolation in `<student_answer>`-Tags, keine Interpolation in System-Nachrichten.
- Nur Modelle aus `ALLOWED_MODELS` sind über Request-Parameter wählbar.
- Tatsaechlich bereitgestellte autoritative Bewertung bleibt verbindlich;
  Modellhypothesen und synthetische Fehlerkontexte sind keine solchen Urteile.
- Hilfestufen sind im Default interne Tutorsteuerung. `TUTOR_HIDE_HINT_LEVEL=0`
  deaktiviert die Outputregel fuer Vergleichszwecke; `DEBUG_MODE` steuert
  unabhaengig davon die HTML-Anzeige.
- API-Keys nur über `.env`/Umgebung; niemals loggen oder committen.
- Aufgabenstellung und Rückfragen stehen ausschließlich im User-Kontext, nie in der Systemrolle. Jinja2 escaped auch Debug-Prompts und Chatbeiträge.
- Die Referenz-Doppelfreigabe bleibt aktiv. Defaultstufe 3 uebermittelt
  hoechstens drei Schritte; Mengenlimits sind konfigurierbar und stoppen vor
  einem literal gesperrten Endantwortschritt. Keine semantische Outputgarantie.
