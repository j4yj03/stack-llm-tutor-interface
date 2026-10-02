# Ordner `code/app/templates/`

Stand: 2026-10-02. Jinja2-Templates der Weboberflaeche. Der HTML-Vertrag
ist kleiner als der JSON-/Evaluationsvertrag; nicht angezeigte Metadaten
werden dadurch nicht automatisch falsch oder erfunden. Details:
[../README.md](../README.md), [../../config/README.md](../../config/README.md).

## `tutor_page.html`

Wird von `main.py` über `GET /start` (Moodle/STACK-Adapter) und
`POST /tutor/{chat_id}/message` sowie `/tutor/{chat_id}/retry` gerendert.
Alle verwenden `render_tutor_page`
und denselben gespeicherten `StackContext`.

### Vom Template genutzte Kontextvariablen

| Variable | Quelle | Zweck |
|---|---|---|
| `question_id`, `question_text` | gespeicherter StackContext; ursprünglich Moodle-Text oder Task-JSON | Aufgabenanzeige (Rohdaten, z. B. fuer Tests/Debug) |
| `question_text_display` | `question_display_text` aus `main.py` | Anzeigetext: komponierte `{funktion}` als LaTeX in `\( \)`, sonst unverändert |
| `student_answer` | Gespeicherter StackContext aus `ans1` | Urspruengliche bereitgestellte Antwort; kein Beleg einer Bewertung; roh im `<code>`-Fallback |
| `student_answer_latex` | `cas_to_latex` der Antwort | Anzeige als Formel, wenn der Antworttext ein reiner STACK-Ausdruck ist, sonst `None` |
| `diagnosis_code`, `diagnosis_title` | Gespeicherter bereitgestellter Kontext | Historische Debuganzeige `STACK-Diagnose`, kein Verifizierungsbeleg |
| `hint_level` | GET-Parameter bzw. Chat-State | Debug-Anzeige und Formularmechanik; für Studierende nicht sichtbar |
| `model` | Modell-Allowlist-Auswahl | bleibt bei Folgehints erhalten |
| `history` | ChatStore | sichtbare User-/Tutor-Beiträge, keine Systemnachrichten |
| `max_hint_level` | Konfigurierter `MAX_HINT_LEVEL` (Default 4) | Stufenauswahl ab gespeicherter aktueller Stufe, auch 0 |
| `chat_id` | UUID der Session | Session-Identität |
| `prompt` | JSON der tatsächlich verwendeten Rollennachrichten | einklappbare Debug-Anzeige; `None`, wenn keine Generierung erfolgte |
| `context_options` | JSON der ContextOptions des letzten Generierungsversuchs | Debug-Anzeige; `None`, wenn keine Generierung erfolgte |
| `error`, `message_draft` | Validierung/LLM-Fehler | Fehlermeldung und bei ungültiger Eingabe begrenzter Entwurf |
| `debug_mode` | `DEBUG_MODE` aus config.py | blendet den kompletten Debug-Bereich (STACK-Diagnose, Hilfestufen-Dropdown, Prompt-/Options-Debugger) aus (0), ohne den LLM-Kontext zu ändern |
| `retry_hint_level`, `retry_inline`, `retry_in_error` | serverseitig aus Fehler + Verlauf | Platzierung des Retry-Formulars (Chatblase bzw. Fehlerbox) und Zielstufe |
| `max_chat_message_length` | `MAX_CHAT_MESSAGE_LENGTH` aus config.py | Textarea-Limit |

### Verhalten

- Formular "Nachricht senden" laedt Verlauf und neuen Prompt per HTML-POST.
  Bei deaktivierter Adaption (Default) bleibt die Stufe gleich; eingeschaltet
  kann Zeit plus Selbstbericht beim naechsten POST eine Erhoehung begruenden.
  Erst erfolgreicher Hint commitet die Zielstufe; kein autonomer Timer.
  Das Template zeigt die Stufe nur im Debugbereich. Das LLM-Verbot ihrer
  Nennung steuert separat `TUTOR_HIDE_HINT_LEVEL`, Default `true`.
- Nach einer fehlgeschlagenen Generierung erscheint genau ein Retry-Formular („Erneut versuchen“): inline in der Chatblase der unbeantworteten Frage, sonst in der Fehlerbox (z. B. nach fehlgeschlagenem `/start`). Versteckte Felder: `model` und `hint_level` (Versuchsstufe, nie unter der gespeicherten Stufe). Ein Retry ändert die Frage nicht und hängt bei Erfolg nur die Tutor-Antwort an.
- Aufgabe und „Deine Antwort“ teilen sich eine Bubble. Eine separate „Weitere Hilfe“-Bubble existiert nicht mehr.
- Hilfestufen-Dropdown im Debug-`<details>`: ruft erneut `GET /start` mit **derselben `chat_id`** und der gewählten Stufe auf (aktuelle Stufe vorausgewählt, Auswahl bis `MAX_HINT_LEVEL`). Die Aufgabe bleibt im serverseitigen Kontext; sie wird nicht erneut in Hidden-Feldern transportiert. Bei `MAX_HINT_LEVEL` entfällt das Formular.
- Modellwahl bleibt in allen Formularen erhalten. URLs werden mit `request.url_for` erzeugt.
- Die Seite funktioniert bei deaktiviertem JavaScript; Formulare sind
  JavaScript-frei. Für die Formelanzeige lädt sie KaTeX `0.19.0` per CDN
  (jsDelivr) mit SRI-`integrity` und `crossorigin="anonymous"`. Das
  `<meta name="referrer" content="no-referrer">` verhindert, dass die
  `/start`-URL (mit Studierendenantwort) als Referer an den CDN-Host geht.
  Ohne erreichbares CDN bleibt alles lesbarer Text mit TeX-Delimitern.
- KaTeX rendert `\( \)`, `$$ $$`, `\[ \]` und `$ $`. `<pre>`, `<code>` und
  `<textarea>` werden nicht gesetzt — der Debug-Prompt und Eingabefelder
  bleiben roh. Für Tutorhinweise fordert die konfigurierbare Regel
  `TUTOR_LATEX_NOTATION=1` (Tutorprompt) LaTeX-Ausgabe an. Fehlformate bricht
  `errorCallback` als Konsolenwarnung ab, statt die Seite zu stören.
  Jinja2-Escaping bleibt vollständig aktiv; KaTeX liest nur Textknoten.
- Reine STACK-/Maxima-Ausdrücke (CAS-Syntax wie `6*x^5`, `2*%e^(x^6-6*%e^x)`,
  `f(x)=...`) werden **nur fuer die Anzeige** serverseitig nach LaTeX
  konvertiert (`app/math_notation.py`, stdlib-AST-Whitelist, kein eval):
  Aufgabe (komponierte `{funktion}`), „Deine Antwort" und reine
  Ausdrucks-Nachrichten im Chat. Nicht erkennbare Eingaben (Prosa, unbekannte
  Syntax, `!!`, unbekannte `%`-Konstanten) bleiben roh bzw. im `<code>`-Element.
  Gespeicherter Kontext und LLM-Prompts enthalten weiterhin die CAS-Syntax;
  die Anzeige hat keine Auswirkung auf Evaluation/Reproduzierbarkeit.
- Debug-`<details>` zeigt den gespeicherten Diagnosekontext, Stufendropdown und
  tatsaechlichen Hintprompt sowie Optionsdaten. Auf erfolgreichen Generierungen
  werden effektive Flags nach Stage-0-/Diagnosefilter angezeigt; in den
  bestehenden HTML-Fehlerpfaden kann das Optionsfeld noch angeforderte Defaults
  zeigen. Es ist kein vollstaendiges reproduzierbares Operationsjournal.
  `DEBUG_MODE=0` blendet diese Ansicht aus, aendert aber den Prompt nicht;
  der manuelle Stufenselektor entfaellt, REST-Folgehints bleiben verfuegbar.
  Gewoehnliche Rueckfragen koennen bei eingeschalteter Adaption trotzdem
  aufsteigen. Ungueltige Nachrichten erzeugen keinen neuen Prompt.
- Solange eine Chatfrage unbeantwortet ist (Retry inline verfügbar), ist der Senden-Knopf des Chat-Formulars deaktiviert und der Hilfe-Text verweist auf „Erneut versuchen“; nach erfolgreichem Retry wird er wieder aktiv.
- HTML-Escaping von Jinja2 ist auch für Chat, Fehlermeldungen und `<pre>` aktiv; kein `safe`-Filter. Systemnachrichten aus dem gespeicherten Verlauf werden nicht als Chatbeiträge angezeigt.
- HTTP 429/502 bleiben Fehlerstatus, liefern aber die Tutor-Seite mit Verlauf, Formular und fester Fehlermeldung. Die erfolglose Frage bleibt gespeichert; ein erneutes Absenden erzeugt einen neuen User-Beitrag.

### Verifikation

TestClient-Regressionstests verwenden temporaere SQLite-Datenbanken und
Fake-LLMs. Historisch wurden Desktop-/Mobile-Formularablaeufe ohne JavaScript
in Headless Edge 153 geprueft. Diese fruehere UI-Pruefung belegt weder die
neuen Start-/Adaptionsbedingungen noch aktuelle Notebook-/Deploymenttests.
Keine pauschale Passzahl behaupten. Echte Moodle-/STACK-Abnahme steht separat
in [../../moodle/README.md](../../moodle/README.md).

### Aktuelle Grenzen

- `/start` ohne explizites Level nutzt feste/individuelle Serverstartwahl;
  ein konfiguriertes `TUTOR_START_LEVEL=0` startet neue Chats in der
  Diagnosephase. Die Moodle-Snippets senden keine Stufe und folgen der
  Serverstartwahl; bestehende Chats behalten ihre gespeicherte Stufe.
- `general` und strukturierte Antworten verwenden dasselbe Template. Es
  zeigt weiterhin die historischen Tutorbezeichnungen; dies ist kein zweiter
  Promptpfad und keine aktivierte Tutorpolicy im General-Modus.
- Bei `structured` wird `hint` angezeigt/gespeichert; eine separate
  `diagnosis_hypothesis`, Baseline, Startentscheidung, Auswahlmessages und
  Config-/Policyhashes werden aktuell nur in JSONmetadaten angeboten.
- Die Debugueberschrift `STACK-Diagnose` macht synthetischen oder URL-Kontext
  nicht zu einem PRT-Ergebnis. Sichtbare Daten sind zu escapen, Herkunft und
  Unsicherheit fuer fachliche Vergleiche aus API/Korpus kontrollieren.
- `TUTOR_HIDE_HINT_LEVEL=0` erlaubt dem LLM fuer Vergleichszwecke die Nennung;
  es schaltet nicht die HTML-Debuganzeige ein. `DEBUG_MODE=0` ist umgekehrt
  keine Authentifizierung oder JSON-Debugsperre.
- Ein Retry ist UI-Hilfe, kein dauerhafter Fehlernachweis oder idempotentes
  Replay. Deshalb darf der Evaluationsrunner fehlgeschlagene Folge-POSTs nicht
  einfach anhand eines gerenderten Retrybuttons automatisch wiederholen.

### Änderungen

Neue Kontextvariablen erfordern Anpassungen in `main.py` (TemplateResponse-Kontext) und ggf. in `tests/test_api.py`.
