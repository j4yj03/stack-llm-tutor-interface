# Ordner `code/app/templates/`

Jinja2-Templates der Weboberfläche.

## `tutor_page.html`

Wird von `main.py` über `GET /start` (Moodle/STACK-Adapter) und
`POST /tutor/{chat_id}/message` gerendert. Beide verwenden `render_tutor_page`
und denselben gespeicherten `StackContext`.

### Vom Template genutzte Kontextvariablen

| Variable | Quelle | Zweck |
|---|---|---|
| `question_id`, `question_text` | gespeicherter StackContext; ursprünglich Moodle-Text oder Task-JSON | Aufgabenanzeige |
| `student_answer` | gespeicherter StackContext aus `ans1` | ursprüngliche bewertete Antwort |
| `diagnosis_code`, `diagnosis_title` | PRT-Diagnose | Diagnoseanzeige |
| `hint_level` | GET-Parameter bzw. Chat-State | Debug-Anzeige und Formularmechanik; für Studierende nicht sichtbar |
| `model` | Modell-Allowlist-Auswahl | bleibt bei Folgehints erhalten |
| `history` | ChatStore | sichtbare User-/Tutor-Beiträge, keine Systemnachrichten |
| `max_hint_level` | `MAX_HINT_LEVEL` aus config.py | Stufenanzeige |
| `chat_id` | UUID der Session | Session-Identität |
| `prompt` | JSON der tatsächlich verwendeten Rollennachrichten | einklappbare Debug-Anzeige; `None`, wenn keine Generierung erfolgte |
| `context_options` | JSON der ContextOptions des letzten Generierungsversuchs | Debug-Anzeige; `None`, wenn keine Generierung erfolgte |
| `error`, `message_draft` | Validierung/LLM-Fehler | Fehlermeldung und bei ungültiger Eingabe begrenzter Entwurf |
| `debug_mode` | `DEBUG_MODE` aus config.py | blendet den kompletten Debug-Bereich (STACK-Diagnose, Hilfestufen-Dropdown, Prompt-/Options-Debugger) aus (0), ohne den LLM-Kontext zu ändern |
| `retry_hint_level`, `retry_inline`, `retry_in_error` | serverseitig aus Fehler + Verlauf | Platzierung des Retry-Formulars (Chatblase bzw. Fehlerbox) und Zielstufe |
| `max_chat_message_length` | `MAX_CHAT_MESSAGE_LENGTH` aus config.py | Textarea-Limit |

### Verhalten

- Formular „Nachricht senden“ sendet einen HTML-POST und lädt die Seite mit Verlauf und neuem Prompt. Die Hilfestufe bleibt unverändert und wird Studierenden nirgends angezeigt — der Hilfetext nennt sie nicht, die Stufe erscheint nur im Debug-Bereich.
- Nach einer fehlgeschlagenen Generierung erscheint genau ein Retry-Formular („Erneut versuchen“): inline in der Chatblase der unbeantworteten Frage, sonst in der Fehlerbox (z. B. nach fehlgeschlagenem `/start`). Versteckte Felder: `model` und `hint_level` (Versuchsstufe, nie unter der gespeicherten Stufe). Ein Retry ändert die Frage nicht und hängt bei Erfolg nur die Tutor-Antwort an.
- Aufgabe und „Deine Antwort“ teilen sich eine Bubble. Eine separate „Weitere Hilfe“-Bubble existiert nicht mehr.
- Hilfestufen-Dropdown im Debug-`<details>`: ruft erneut `GET /start` mit **derselben `chat_id`** und der gewählten Stufe auf (aktuelle Stufe vorausgewählt, Auswahl bis `MAX_HINT_LEVEL`). Die Aufgabe bleibt im serverseitigen Kontext; sie wird nicht erneut in Hidden-Feldern transportiert. Bei `MAX_HINT_LEVEL` entfällt das Formular.
- Modellwahl bleibt in allen Formularen erhalten. URLs werden mit `request.url_for` erzeugt.
- Die Seite enthält keine Skripte und funktioniert bei deaktiviertem JavaScript. Viewport, umbrechende Formeln/Debug-Daten und eine flexible Textarea unterstützen Mobilgeräte.
- Debug-`<details>` („Debug-Informationen“) enthält die STACK-Diagnose, das Hilfestufen-Dropdown für den nächsten Hinweis sowie den echten Prompt **und die ContextOptions** des letzten Generierungsversuchs, auch bei LLM-Fehlern — alles nur bei `DEBUG_MODE=1`. Bei `DEBUG_MODE=0` bleibt der LLM-Kontext unverändert, nur die Anzeige ist weg; die HTML-Seite bietet dann keinen Folgehint mehr (der REST-Endpunkt `/api/tutor/{chat_id}/next-hint` bleibt verfügbar). Eine ungültige Nachricht erzeugt keinen neuen Prompt und keine Options-Anzeige. Vor produktivem Einsatz mit Studierenden `DEBUG_MODE=0` setzen.
- Solange eine Chatfrage unbeantwortet ist (Retry inline verfügbar), ist der Senden-Knopf des Chat-Formulars deaktiviert und der Hilfe-Text verweist auf „Erneut versuchen“; nach erfolgreichem Retry wird er wieder aktiv.
- HTML-Escaping von Jinja2 ist auch für Chat, Fehlermeldungen und `<pre>` aktiv; kein `safe`-Filter. Systemnachrichten aus dem gespeicherten Verlauf werden nicht als Chatbeiträge angezeigt.
- HTTP 429/502 bleiben Fehlerstatus, liefern aber die Tutor-Seite mit Verlauf, Formular und fester Fehlermeldung. Die erfolglose Frage bleibt gespeichert; ein erneutes Absenden erzeugt einen neuen User-Beitrag.

### Verifikation

TestClient-Regressionstests folgen den gerenderten Formularen mit temporärer
SQLite-Datenbank und Fake-LLM. Zusätzlich geprüft in Headless Edge 153 mit
deaktiviertem JavaScript: HTML-POST, Folgehints bis Stufe 4, exakter Prompt,
Desktop 1280/1440 und Mobile 390 Pixel, lange Formeln ohne horizontales Scrollen.
Das ersetzt keinen Test der separaten STACK-JS-Snippets im echten Moodle.

### Änderungen

Neue Kontextvariablen erfordern Anpassungen in `main.py` (TemplateResponse-Kontext) und ggf. in `tests/test_api.py`.
