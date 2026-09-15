# Ordner `code/schemas/`

JSON-Schema-Definitionen für lokale Datenformate.

## `stack_ai_tutor_task.schema.json`

JSON Schema Draft 2020-12 für Aufgaben-Definitionen. Wird von
`app/task_loader.py` beim Serverstart auf **jede** Datei in `tasks/`
angewendet – ungültige Aufgaben verhindern bewusst den Start (Fail-fast).

### Pflichtfelder (Top-Level)

`schema_version`, `question_id` (Pattern `^[a-zA-Z0-9_\-]+$`),
`status` (`draft|review|published|archived`), `language` (`de|en`),
`topic`, `subtopic`, `question_text`, `learning_goals`,
`student_inputs`, `model_solution`, `diagnoses`, `tutor_policy`,
`hint_levels`, `prompt_context_policy`

### Wichtige Strukturen

- **`student_inputs`**: STACK-Eingaben (Name, Typ wie `algebraic_expression`, Syntaxbeispiele)
- **`model_solution`**: `final_answer`, `solution_steps` (je `step_id`, `description`, optionale `formula`/LaTeX), optionale `equivalent_forms`
- **`diagnoses`**: Map Diagnose-Code → Objekt mit `title`, `severity`, `feedback_goal`, `concept_tags`, `avoid_phrases`, `preferred_hint_strategy`, `allowed_hint_levels`
- **`tutor_policy`**: Ton, Wortgrenzen, `do_not_give_final_answer_on_first_hint`, `forbidden_behaviors`
- **`hint_levels`**: aufgabenspezifische Stufen-Beispiele (Ergänzung zur generischen Policy in `config/`)
- **`prompt_context_policy`**: `solution_step_limit_by_hint_level`, `include_final_answer_from_hint_level`, `treat_student_answer_as_untrusted`

### Änderungsregeln

Jede Schemaänderung muss synchron erfolgen in:

1. dieser Schema-Datei,
2. allen Dateien in `tasks/*.json`,
3. `app/task_loader.py`/`app/main.py` (falls Mapping betroffen),
4. Tests (`test_prompt_builder.py`, `test_task_handler`-Abdeckung),
5. Dokumentation.

`additionalProperties: false` ist überall aktiviert – unbekannte Felder führen zu Validierungs­fehlern.
