# Ordner `code/app/templates/`

Jinja2-Templates der Weboberfläche.

## `tutor_page.html`

Wird von `main.py` über `GET /start` gerendert (Moodle/STACK-Adapter).

### Vom Template genutzte Kontextvariablen

| Variable | Quelle | Zweck |
|---|---|---|
| `question_id`, `question_text` | Task-JSON | Aufgabenanzeige |
| `student_answer` | GET-Parameter `ans1` | angezeigte Antwort |
| `diagnosis_code`, `diagnosis_title` | PRT-Diagnose | Diagnoseanzeige |
| `hint_level` | GET-Parameter bzw. Chat-State | Stufenanzeige (1–4) |
| `model` | Modell-Allowlist-Auswahl | bleibt bei Folgehints erhalten |
| `tutor_answer` | LLM-Antwort | Hinweisbox |
| `history` | ChatStore | bisheriger Verlauf |
| `max_hint_level` | Konstante (4) | Stufenanzeige |
| `chat_id` | UUID der Session | Session-Identität |

### Verhalten

- Formular „Weiterer Hinweis" ruft erneut `GET /start` mit `hint_level+1` auf (max. 4); bei Stufe 4 wird ein Hinweistext statt des Buttons angezeigt.
- Debug-`<details>` zeigt den erzeugten Prompt – nur für Entwicklungszwecke, vor dem produktiven Einsatz entfernen.

### Bekannte Lücken

- Historie wird serverseitig gespeichert, aber im Template noch nicht Chat-funktional dargestellt (kein Eingabefeld, kein `/message`-Formular).
- HTML-Escaping von Jinja2 ist aktiv; Zusicherung nicht entfernen.

### Änderungen

Neue Kontextvariablen erfordern Anpassungen in `main.py` (TemplateResponse-Kontext) und ggf. in `tests/test_api.py`.
