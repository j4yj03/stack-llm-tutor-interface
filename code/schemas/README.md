# Ordner `code/schemas/`

Stand: 2026-10-02. JSON-Schema fuer lokale Aufgaben; nicht identisch mit
den Pydantic-API-Modellen oder dem separaten Evaluationsfallformat.
Beispieldaten: [../tasks/README.md](../tasks/README.md); API:
[../app/README.md](../app/README.md); Evaluation:
[../evaluation/README.md](../evaluation/README.md).

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
- **`hint_levels`**: schemapflichtige historische Stufen-Beispiele, nicht
  zusaetzliche aktive Runtimepolicy. Zentrale Policy und Overrides stehen in
  [../config/README.md](../config/README.md).
- **`prompt_context_policy`**: `solution_step_limit_by_hint_level`, `include_final_answer_from_hint_level`, `treat_student_answer_as_untrusted`

`tutor_policy`, `hint_levels` und `prompt_context_policy` bleiben Legacyfelder.
Ihre vorhandenen `minimum: 1`-Grenzen sind keine Begrenzung der neuen zentralen
Hilfestufen oder API: dort ist `0..MAX_HINT_LEVEL` erlaubt, mit Maximum `0..32`.
Maximum 0 braucht explizit `TUTOR_START_LEVEL=0` statt Default 1. Eine eigene
Policydatei muss Stage 0 explizit enthalten; dafuer keine Legacy-Taskfelder
stillschweigend umdeuten oder entfernen.

### Optionaler Fallblock

`evaluation_examples` ist ein Objekt ohne unbekannte Eigenschaften:

| Feld | Vertrag |
|---|---|
| `instance_id` | ID nach `^[a-zA-Z0-9][a-zA-Z0-9_\-]*$` |
| `function` | Nichtleere explizite instanziierte Funktion fuer `{funktion}`, passend zu `model_solution` |
| `answers` | Mindestens ein authored Antwortobjekt |

Ein Antwortobjekt braucht `case_id`, `student_answer`,
`expected_input_validity` (`valid|invalid|unknown`) und `expected_correctness`
(`correct|incorrect|unknown`). `expected_error` ist optional, `null` oder ein
Diagnosekey. `cases_from_tasks` prueft dessen Referenz sowie eindeutige IDs und
das notwendige Template zusaetzlich zum Schema. Das Schema selbst bewertet
keine Mathematik und prueft keinen ausgefuehrten PRT.

Die Erweiterung ist optional; gueltige Tasks ohne Beispiele bleiben gueltig.
Die aus ihr abgeleiteten Faelle haben Evaluations-`schema_version="1.0"`,
synthetische Provenienz und pending-Verifizierung. Task-`schema_version`
und lokale Publikation sind keine Freigabe dieser Faelle. `math_rules`
bleibt als Top-Level-Feld im Task-Schema unzulaessig, auch wenn API und
Evaluationsmodelle es unterstuetzen.

### API und Evaluation

`app/schemas.py` definiert unabhaengig davon `StackContext` und die zehn
`ContextOptions`. `diagnosis_source` ist optional und erlaubt `synthetic`,
`provided`, `prt`, `stack`, `stack_prt`, `unknown` oder `null`. Es ist kein
elfter Kontextschalter und kein Herkunftsnachweis. JSON-Startstufe ist optional;
`null` aktiviert serverseitige Startwahl, eine Ganzzahl adressiert direkt
eine aktive Stufe. Geschuetzte Simulationsfelder sind keine persoenlichen
Lernzeitmessungen.

`evaluation/models.py` trennt `tutor_context` von `evaluation_only`
(Instanz, Referenz, Verifizierung, Provenienz), verwirft unbekannte Felder und
modelliert Deploymentbedingungen sowie abhaengige Skriptturns. Ein Requestfeld
ist nicht automatisch sichtbarer Promptkontext; beide Referenzfreigaben bleiben
notwendig. Format- und Referenzchecks sind keine symbolische Bewertung.

### Änderungsregeln

Jede Schemaänderung muss synchron erfolgen in:

1. dieser Schema-Datei,
2. allen Dateien in `tasks/*.json`,
3. `app/task_loader.py`/`app/main.py` (falls Mapping betroffen),
4. Tests (`test_task_loader.py`, `test_task_cases.py`, Prompt-/Disclosureschutz),
5. Dokumentation.

Top-Level und strukturierte Taskobjekte weisen unbekannte Felder zurueck.
Absichtlich offene Maps sind `given_data`, `diagnoses` und
`solution_step_limit_by_hint_level`; auch dort gelten die jeweiligen
Wertschemas. Deshalb nicht pauschal `additionalProperties: false` fuer jede
Map behaupten. Schema-/Datenmigrationen muessen Referenzpassung, Variantenschutz
und Forschungsevidenz getrennt halten.
