# Ordner `code/config/`

Generische Tutor-Policy – bewusst **getrennt** von aufgabenspezifischen Daten in `tasks/`.

## `hint_levels.json`

Definiert die vier generischen Hilfestufen, die in `app/hint_policy.py`
geladen und validiert werden (alle Stufen 1..`MAX_HINT_LEVEL` müssen
vollständig vorhanden sein, sonst startet die Anwendung nicht).

### Felder je Stufe

| Feld | Bedeutung |
|---|---|
| `name` | Kurzname der Stufe |
| `goal` | didaktisches Ziel; geht in die System-Nachricht |
| `max_words` | Wortlimit für den LLM-Hinweis |
| `may_include` | erlaubte Inhalte (positiv formulierte Erlaubnisliste) |
| `must_not_include` | verbotene Inhalte |
| `include_solution_steps` | dürfen Lösungsschritte in den Kontext? |
| `include_final_answer` | darf die Musterlösung in den Kontext? |

### Festgelegte Progression

| Stufe | Name | Ziel | max. Wörter | Schritte | Endlösung |
|--:|---|---|--:|---|---|
| 1 | Orientierung | relevantes Konzept aktivieren | 70 | nein | nein |
| 2 | Strukturierung | Aufgabe zerlegen, Regel benennen | 100 | nein | nein |
| 3 | Nächster Rechenschritt | einen konkreten Schritt ermöglichen | 130 | ja | nein |
| 4 | Ausführliche Unterstützung | Lösungsweg erläutern | 220 | ja | ja |

### Regeln

- **Keine aufgabenspezifischen Inhalte** (keine Formeln für einzelne Aufgaben) in dieser Datei; fachspezifische Hinweise gehören in `tasks/*.json`.
- Die Flags bilden zusammen mit `ContextOptions` im Prompt-Builder die **Doppelprüfung** für Lösungspreisgabe: Ein Abschnitt erscheint nur, wenn Option **und** Stufe beide `true` sind.
- Passende Tests: `code/tests/test_hint_policy.py` und `code/tests/test_solution_disclosure.py`.
