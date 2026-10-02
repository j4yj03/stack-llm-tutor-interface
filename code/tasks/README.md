# Ordner `code/tasks/`

Stand: 2026-10-02. Lokale Aufgaben-Definitionen fuer den KI-Tutor. Jede Datei ist eine
JSON-Aufgabe und wird beim Serverstart durch `app/task_loader.py`
gegen `schemas/stack_ai_tutor_task.schema.json` validiert.
Formatvertrag: [../schemas/README.md](../schemas/README.md); generische
Laufzeitpolicy: [../config/README.md](../config/README.md).

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
- Diagnosen: `diagnoses` als Katalog erlaubter Fehlercodes und Titel, mit
  `unknown_error` als Laufzeitfallback. Ein Katalogeintrag ist keine ausgefuehrte
  PRT-Pruefung; seine Verwendung als synthetischer Fehlerkontext muss erkennbar sein.
- Legacyfelder `tutor_policy`, `hint_levels`, `prompt_context_policy` bleiben
  schemapflichtig, sind aber weder aktive generische Runtimepolicy noch
  zusaetzliche task-spezifische Eskalationsregeln. `HintPolicy` ist massgeblich.
- Optional `evaluation_examples`: explizite feste Funktion und authored
  Antwortvarianten passend zur lokalen `model_solution`; nur fuer Offlineableitung.

Die Aufgaben gelten als `published` im lokalen Taskformat. Das ist nicht
gleichbedeutend mit `readiness="released"` oder mathematischer/diagnostischer
Verifizierung eines Evaluationsfalls. `math_rules` ist aktuell kein erlaubtes
Top-Level-Taskfeld; nicht ohne synchronisierte Schemamigration hinzufuegen.

## Evaluationsbeispiele

`evaluation_examples` enthaelt genau eine explizite feste Aufgabeninstanz
pro Task mit `instance_id`, `function` und `answers`. Die Funktion wird im
`question_text_template` eingesetzt, nicht aus Studentantworten oder der
Endloesung erraten. Referenzendloesung, Aequivalentformen und geordnete Schritte
stammen aus der **zu genau dieser Funktion passenden** `model_solution`.
Schema-Gueltigkeit beweist diese mathematische Passung nicht; ohne belegte
Pruefung bleibt sie pending. Weitere Funktionen brauchen eigene instanzspezifische Referenzen,
nicht die Wiederverwendung der festen Beispielendloesung.

| Task | Explizite Funktion | Antworten |
|---|---|---:|
| `ableitung_kettenregel_exp_001` | `f(x)=-5*exp(x^2-2*exp(x))` | 9 |
| `ableitung_produktregel_001` | `f(x)=x^2*sin(x)` | 6 |

Die 15 Faelle umfassen Fehler-, Syntax-, Unknown- und korrekte Kontrollen.
Jede authored Antwort enthaelt `case_id`, `student_answer`,
`expected_input_validity` und `expected_correctness`; optional `expected_error`
als vorhandener Diagnosekey. `null` oder Weglassen bedeutet keine
bereitgestellte Diagnose, nicht automatisch `unknown_error` und nicht eine
nachtraeglich aus der Formel berechnete Diagnose.

Offlineexport aus `code/`, in einen vorhandenen Ausgabeordner:

```bash
python -m evaluation cases-from-tasks --tasks-dir tasks \
    --output evaluation/imports/task_cases.jsonl
```

Eine vorhandene Datei wird nur mit explizitem `--overwrite` ersetzt. Das
Werkzeug validiert alle Tasks, verwirft doppelte Task-/Instanz-/Case-IDs und
unbekannte Fehlerkeys; Tasks ohne diesen optionalen Block tragen keine Faelle
bei. Kein Appimport, keine Datenbank, kein STACK/PRT, kein Provideraufruf.

Ausgaben bleiben `draft`, `response_origin="synthetic_fixture"`,
`mathematics_status="pending"`, `diagnosis_status="pending"`, `score=null`,
`seed=null`. Fehlertitel werden als synthetischer Kontext ohne STACK/PRT-Pruefung
markiert. Referenzen bleiben `evaluation_only`, bis ein Kontextprofil
ausdruecklich Schritte/Endloesung anfordert. Kontrollierte Live-Vergleiche
brauchen beide Opt-ins `allow_unverified_cases=true` und
`allow_task_derived_cases=true`; diese verleihen keine Verifizierung.
Solche Livevergleiche sind gueltige kontrollierte empirische Untersuchungen
ohne PRT-Voraussetzung, nicht Nachweise verifizierten Gradings. Der gemeinsame
Korpuspayload normalisiert synthetische Herkunft auch fuer CLI-Faelle zu
API-`diagnosis_source="synthetic"`.
Vergleich und getrennte Ratings: [../evaluation/README.md](../evaluation/README.md).

## Neue Aufgabe hinzufügen

1. Neue `*.json`-Datei anlegen (Name = `question_id` gewünscht-kanonisch).
2. `question_id` muss einmalig sein (Duplikate → Startfehler).
3. `unknown_error`-Diagnose **zwingend** definieren (Fallback in `main.py`).
4. Diagnosekeys fuer eine echte Moodleintegration mit deren PRT-Codes
   abstimmen, ohne authored Beispiele als PRT-Evidenz zu deklarieren.
5. Offlinevalidierung mit Taskloader-/Taskcase-Tests pruefen. Serverstart und
   `GET /tasks` sind zusaetzliche Deploymentchecks, keine mathematische Abnahme.
6. Stage 0 und weitere generische Stufen in der zentralen Policy konfigurieren,
   nicht in Legacy-Taskstufen duplizieren. Referenzen einer Moodle-Zufallsvariante
   werden durch den normalen `/start`-Pfad weiterhin nicht angehaengt.
