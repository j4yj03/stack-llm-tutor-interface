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
| `max_solution_steps` | maximale Anzahl der ersten Lösungsschritte; nichtnegative Ganzzahl oder `null` für alle |
| `include_final_answer` | darf die Musterlösung in den Kontext? |

### Festgelegte Progression

| Stufe | Name | Ziel | max. Wörter | Schritte | Endlösung |
|--:|---|---|--:|---|---|
| 1 | Orientierung | relevantes Konzept aktivieren | 70 | nein | nein |
| 2 | Strukturierung | Aufgabe zerlegen, Regel benennen | 100 | nein | nein |
| 3 | Nächster Rechenschritt | einen konkreten Schritt ermöglichen | 130 | max. 3 | nein |
| 4 | Ausführliche Unterstützung | Lösungsweg erläutern | 220 | ja | ja |

### Regeln

- **Keine aufgabenspezifischen Inhalte** (keine Formeln für einzelne Aufgaben) in dieser Datei; fachspezifische Hinweise gehören in `tasks/*.json`.
- Die Flags bilden zusammen mit `ContextOptions` im Prompt-Builder die **Doppelprüfung** für Lösungspreisgabe: Ein Abschnitt erscheint nur, wenn Option **und** Stufe beide `true` sind.
- Passende Tests: `code/tests/test_hint_policy.py` und `code/tests/test_solution_disclosure.py`.

### Migration und Grenzen

`max_solution_steps` ist ein neues Pflichtfeld der **generischen** Policy.
Bestehende eigene Konfigurationen um die Werte `0`, `0`, `3`, `null` für die
Stufen 1 bis 4 ergänzen. Ohne Feld schlägt das Laden bewusst fehl. Task-JSON und
SQLite-Format ändern sich nicht; die alten task-spezifischen `hint_levels` und
`prompt_context_policy` werden weiterhin nicht zur generischen Steuerung verwendet.

Vorher wurden auf Stufe 3 alle Lösungsschritte übertragen, einschließlich eines
Schritts mit dem Endergebnis. Das konnte die Endlösung trotz ausgeschaltetem
`include_final_answer` offenlegen. Jetzt gilt zusätzlich das zentrale Mengenlimit.
Wenn die Endlösung nicht durch **beide** Freigaben erlaubt ist, endet die Liste
vor dem ersten Schritt, der die konkrete `final_answer`-Zeichenfolge enthält.

Dies ist keine symbolische Äquivalenzprüfung. Anders geschriebene Lösungen in
Schritten/Verlauf und vom LLM selbst erzeugte vollständige Lösungen werden damit
nicht zuverlässig erkannt. Die verifizierten Schritte weiterhin passend ordnen
und prüfen; Output-Prüfung per STACK/Maxima bleibt ein separater Arbeitspunkt.
