# Ordner `code/tasks/`

Lokale Aufgaben-Definitionen für den KI-Tutor. Jede Datei ist eine
JSON-Aufgabe und wird beim Serverstart durch `app/task_loader.py`
gegen `schemas/stack_ai_tutor_task.schema.json` validiert.

## Enthaltene Aufgaben

| Datei | `question_id` | Thema | Regeln |
|---|---|---|---|
| `ableitung_kettenregel_exp_001.json` | `ableitung_kettenregel_exp_001` | Ableitungen / Kettenregel bei Exponentialfunktionen | Kettenregel, Potenzregel, Konstantenfaktor |
| `ableitung_produktregel_001.json` | `ableitung_produktregel_001` | Ableitungen / Produktregel | Produktregel, innere Ableitung |

## Aufbau (Kurzfassung)

- Identität & Einordnung: `question_id`, `status`, `language`, `topic`, `subtopic`, `difficulty`
- Inhalt: `question_text` (generische Anweisung ohne konkrete Funktion), `question_text_template` (Satzbaustein mit `{funktion}`-Platzhalter), `question_latex`, `given_data` (generisch, z. B. nur `variable`), `learning_goals`, `prerequisites`
- STACK-Bindung: `student_inputs` (z. B. `ans1` als `algebraic_expression`); die konkret instanziierte Funktion kommt aus Moodle/STACK (`funktion`-Parameter)
- Musterlösung: `model_solution.final_answer` + `solution_steps` mit `step_id`, `description`, `formula` — **lokale Beispieldaten eines festen Beispiels**, werden bei Moodle-Varianten nie verwendet
- Diagnosen: `diagnoses` mit PRT-Fehlercodes (incl. `unknown_error` als Pflicht-Fallback), je Eintrag `severity`, `feedback_goal`, `avoid_phrases`, `allowed_hint_levels`
- Tutor-Policy: `tutor_policy` (Ton, Wortgrenzen, verbotene Verhaltensweisen)
- Stufen-Beispiele: `hint_levels` (aufgabenspezifisch, ergänzt die generische `config/hint_levels.json`)
- Kontext-Policy: `prompt_context_policy` (Lösungspreisgabe pro Stufe, `treat_student_answer_as_untrusted`)

## Neue Aufgabe hinzufügen

1. Neue `*.json`-Datei anlegen (Name = `question_id` gewünscht-kanonisch).
2. `question_id` muss einmalig sein (Duplikate → Startfehler).
3. `unknown_error`-Diagnose **zwingend** definieren (Fallback in `main.py`).
4. Diagnose-Codes mit den PRT-Codes in der Moodle-Frage (`code/moodle/`) synchron halten.
5. Serverstart ist der Validierungstest: `python -m uvicorn app.main:app`; zusätzlich `GET /tasks` prüfen.
