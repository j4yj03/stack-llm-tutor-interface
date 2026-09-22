# Paket `code/app/`

FastAPI-Anwendung des KI-Tutors. Entrypoint: `app.main:app`.

## Datenfluss

```text
Moodle/STACK → GET /start → main.py
    → task_loader (Aufgabe laden, validieren)
    → ChatStore (Session per UUID anlegen/fortsetzen)
    → HintPolicy (generische Stufen-Regeln)
    → PromptBuilder (System- + Kontext-Nachrichten)
    → app.llm (Backend-Fabrik → SAIA/Ollama)
    → ChatStore (Antwort speichern)
    → tutor_page.html / JSON-Antwort
```

## Dateien

| Datei | Verantwortung |
|---|---|
| `main.py` | FastAPI-Entrypoint; alle REST-Endpunkte; Validierung von `qid`, `diagnosis`, `ans1`, Modell-Allowlist; Fehlermapping LLM→HTTP (429/502) |
| `config.py` | Zentrale Konfiguration: Pfade, `LLM_*`-Umgebungsvariablen, `ALLOWED_MODELS`, Limits für Antworten, Aufgabentext, Chatnachrichten, Verlauf und Hilfestufen |
| `schemas.py` | Pydantic-Modelle: `ContextOptions`, `StackContext`, `TutorRequest`, `NextHintRequest`, `UserChatRequest`, `ChatMessage`, `TutorResponse`, `ChatHistoryResponse` |
| `database.py` | `initialize_database()`, `get_connection()`; SQLite mit Foreign Keys (`ON DELETE CASCADE`) |
| `chat_store.py` | CRUD für Chats/Nachrichten; UUID-Validierung; `next_hint_level` stoppt bei `MAX_HINT_LEVEL` |
| `hint_policy.py` | Lädt `config/hint_levels.json`; prüft Stufen 1..4 vollständig; `HintPolicyError` bei Fehlern |
| `prompt_builder.py` | System-Nachricht (Tutorrolle, Stufenregeln, Prompt-Injection-Schutz) + Kontext-Abschnitte je nach `ContextOptions`; Doppelprüfung bei `solution_steps`/`final_answer` (Option **und** Stufe) |
| `task_loader.py` | Lädt `tasks/*.json`, validiert gegen JSON-Schema (Draft 2020-12), erzwingt eindeutige `question_id`s; Fail-fast bei ungültigen Dateien |
| `ollama_client.py` | Kompatibilitäts-Wrapper (`call_ollama_chat` u. a. delegieren an `app.llm.create_llm_client`) |

## Endpunkte (main.py)

| Route | Methode | Zweck |
|---|---|---|
| `/health` | GET | Health-Check inkl. geladener Aufgaben und Default-Modell |
| `/tasks` | GET | Liste der verfügbaren Aufgaben |
| `/start` | GET | Moodle/STACK-Adapter (HTML-Seite) |
| `/tutor/{chat_id}/message` | POST | Formular-Rückfrage; rendert Chat und Debug-Prompt ohne JavaScript |
| `/api/tutor/start` | POST | Tutor-Session starten |
| `/api/tutor/{chat_id}/next-hint` | POST | Nächste Hilfestufe (inkrementiert, max. 4) |
| `/api/tutor/{chat_id}/message` | POST | Folgefrage stellen (Stufe bleibt gleich) |
| `/api/tutor/{chat_id}/history` | GET | Chatverlauf abrufen |

## Kontext und Chat

`GET /start` akzeptiert weiterhin `qid`, `diagnosis`, `ans1`, `hint_level`,
`model`, `chat_id` sowie optional `frage`-Kontext in zwei Varianten:

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
HTML-Flows aktivieren `include_learning_goals`, sodass die generischen
Lernziele in den Prompt fließen. Die Aufgaben-JSON liefert weiterhin den
Katalog der erlaubten Diagnosen.

Bei bestehendem `chat_id` muss die Kombination aus Aufgabe (Volltext oder
komponierter Text), Antwort und Diagnose zum gespeicherten Kontext passen.
HTML-bedingte LF/CRLF-Unterschiede der Antwort sind erlaubt. Geänderte
Aufgaben/Antworten brauchen einen neuen Link ohne `chat_id`. Nicht erneut
übergebene `question_text`/`funktion` werden aus dem Chat geladen. Niedrigere
Hilfestufen bestehender Chats werden abgewiesen, damit ein alter Stufe-4-Verlauf
nicht als Stufe-1-Kontext verwendet wird.

`POST /tutor/{chat_id}/retry` wiederholt ausschließlich eine fehlgeschlagene
Generierung: Die gespeicherte Nutzerfrage wird **nicht** erneut eingetragen;
bei Erfolg landet nur die neue Assistant-Antwort im Verlauf und die
Ziel-Hilfestufe wird gesetzt. Das Formfeld `hint_level` (optional) bestimmt
die Zielstufe — nie niedriger als die gespeicherte Stufe, sonst HTTP 400;
ein fehlgeschlagener Stufenaufstieg wird also auf der Versuchsstufe
wiederholt. Das Formular erscheint inline **neben der unbeantworteten
Frage** in der Chatblase; existiert keine Chatfrage (typischer
`/start`-Fehler), steht es in der Fehlerbox. Jeder Retry verbraucht einen
LLM-Aufruf, ein Doppelklick erzeugt entsprechend mehrere Antworten;
Idempotenz-Token gibt es bewusst nicht.

`POST /tutor/{chat_id}/message` nimmt `message` und optional `model` als
`application/x-www-form-urlencoded` entgegen (`python-multipart` erforderlich).
Nachrichtenlimit: `MAX_CHAT_MESSAGE_LENGTH`, standardmäßig 2000 Zeichen.
Leere/zu lange Nachrichten werden vor Speicherung mit einer HTML-Fehlermeldung
abgewiesen. Bei LLM-Fehlern bleibt die bereits gespeicherte Frage im Verlauf;
HTTP 429/502 liefern weiterhin eine nutzbare HTML-Seite mit sicherem Fehlertext
und dem Prompt des Versuchs. Folgehints erhöhen die Stufe erst nach erfolgreicher
Generierung. Ein Browser-Neuladen nach einem POST kann erneut senden; es gibt
noch keine idempotenten Requests oder ein Post/Redirect/Get-Archiv.

## LLM-Fehlerverhalten

Der SAIA-Client versucht jeden Chat-Aufruf einmal; schlägt er mit einem
Verbindungs-/HTTP-5xx-Fehler fehl und enthält der Request das vLLM-spezifische
Feld `chat_template_kwargs`, wird **einmal** ohne dieses Feld wiederholt
(Wartezeit: `LLM_RETRY_DELAY`, Standard 2 Sekunden). Hintergrund: Manche
Gateways antworten auf das Feld mit HTTP 500 und leerem Body (siehe
AGENTS.md, Known Issue 8). Steht `LLM_DISABLE_THINKING=0`, entfällt das Feld
von vornherein und es gibt keinen Fallback-Versuch.

Sowohl `main.py` (Rate-Limit, generische LLM-Fehler) als auch der SAIA-Client
(Fallback-Fälle) loggen die Ursache serverseitig mit (`logger.warning`,
inklusive HTTP-Status und Antwortauszug der Plattform, ohne Keys oder
Auth-Header). Studierende sehen weiterhin nur die allgemeine Fehlermeldung
sowie den versuchten Prompt. Bleiben 5xx-Fehler bestehen, SAIA-Dashboard
prüfen, `LLM_MODEL` wechseln oder `LLM_DISABLE_THINKING=0` setzen.

## Debug-Prompt

`generate_hint` gibt `(tutor_answer, messages)` zurück. Der Prompt wird nur einmal
aufgebaut und vor dem Speichern der neuen Tutorantwort angezeigt, nicht aus dem
späteren Verlauf rekonstruiert. `HintGenerationError` trägt die Nachrichten eines
fehlgeschlagenen Versuchs für die HTML-Anzeige, ohne Upstream-Fehlerkörper
weiterzureichen. `render_tutor_page` liest Anzeige und Verlauf aus demselben Chat.

Die drei JSON-Generierungsrouten liefern additiv
`prompt_messages: Optional[List[Dict[str, str]]]` sowie
`context_options: Optional[Dict[str, bool]]` (die beim Aufruf verwendeten
`ContextOptions`, inklusive der Defaults); das History-Format bleibt
unverändert. Beispiel: `[{"role": "system", "content": "..."},
{"role": "user", "content": "..."}]`. Keine API-Keys oder Header darin aufnehmen.
Debug-Prompts sind Entwicklungsdaten, kein dauerhaftes Request-Logging.

Der HTML-Debug-Block zeigt dieselben Daten: die verwendeten ContextOptions als
JSON (`debug-context-options`) und den Prompt (`debug-prompt`). Bei fehlender
Generierung (z. B. abgewiesene Nachricht) bleiben beide leer.

## Sicherheitsregeln

- Studierendenantworten sind **nicht vertrauenswürdig**: Längenlimit, Isolation in `<student_answer>`-Tags, keine Interpolation in System-Nachrichten.
- Nur Modelle aus `ALLOWED_MODELS` sind über Request-Parameter wählbar.
- Das LLM darf STACK-Score, PRT-Diagnose und Bewertungsinstanz nicht überschreiben.
- API-Keys nur über `.env`/Umgebung; niemals loggen oder committen.
- Aufgabenstellung und Rückfragen stehen ausschließlich im User-Kontext, nie in der Systemrolle. Jinja2 escaped auch Debug-Prompts und Chatbeiträge.
- Die Lösungsschutz-Doppelprüfung bleibt aktiv; zusätzlich begrenzt die zentrale Policy die Lösungsschritte auf Stufe 3. Details und Grenzen in `../config/README.md`.
