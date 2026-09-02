# Auswertung: Kontextsteuerung und Erweiterbarkeit

## 1. Zusammenfassung

Diese Auswertung analysiert, ob der aktuelle Code die in der Dokumentation
formulierten Anforderungen an eine **minimale und erweiterbare LLM-Kontextsteuerung**
erfüllt.

**Ergebnis:** Der Code erfüllt diese Anforderung **nicht vollständig**.
Es bestehen Diskrepanzen zwischen Dokumentation und Implementierung.

---

## 2. Anforderungen aus der Dokumentation

### 2.1 Minimaler Kontext (ai_tutor_stack_masterarbeit.md)

Die Dokumentation beschreibt den Informationsfluss:

```text
Moodle/STACK → Link mit qid, diagnosis, ans1 → AI-Tutor-Server
```

Der Server soll dann **aufgabenspezifische Daten laden** und den Kontext
dynamisch aufbauen. Der Link selbst soll nur minimale dynamische Daten enthalten.

### 2.2 Experimentelle Kontextbedingungen (softwarearchitektur.md)

Die Dokumentation beschreibt flexibel kombinierbare Kontextbedingungen:

| Bedingung | Beschreibung |
|-----------|--------------|
| A | Aufgabe + Antwort |
| B | Aufgabe + Antwort + Diagnose |
| C | Aufgabe + Antwort + Diagnose + PRT-Feedback |
| D | zusätzlicher Fachkontext |
| E | zusätzliche Lösungsschritte |

### 2.3 Doppelte Sicherheitsprüfung (softwarearchitektur.md)

Lösungsschritte nur bei **beiden** Bedingungen:

```text
ContextOptions.include_solution_steps = true
UND
Hint-Policy.include_solution_steps = true
```

---

## 3. Analyse des aktuellen Codes

### 3.1 Problem: Hart kodierte ContextOptions (main.py:326-337)

```python
context_options = ContextOptions(
    include_question_text=True,
    include_student_answer=True,
    include_diagnosis_code=True,
    include_prt_feedback=True,
    include_score=False,
    include_learning_goals=False,
    include_math_rules=False,
    include_solution_steps=True,   # Problem!
    include_final_answer=True,     # Problem!
    include_chat_history=True
)
```

**Auswirkung:** Bei jedem /start-Aufruf werden solution_steps und final_answer
mitgesendet, **auch auf Hinweisstufe 1**.

### 3.2 Problem: Nicht genutzte Task-Policy

Die Task-JSON (ableitung_kettenregel_exp_001.json) enthält:

```json
"prompt_context_policy": {
    "solution_step_limit_by_hint_level": {
        "1": 0,
        "2": 1,
        "3": 3,
        "4": 99
    },
    "include_final_answer_from_hint_level": 4
}
```

**Der Code ignoriert diese komplett.** Er verwendet stattdessen die globale
`config/hint_levels.json`.

### 3.3 Was funktioniert

| Komponente | Status |
|------------|--------|
| ContextOptions mit boolschen Flags | Implementiert |
| PromptBuilder prüft ContextOptions | Implementiert |
| Doppelte Prüfung für solution_steps | Implementiert (aber nicht vollständig genutzt) |
| Doppelte Prüfung für final_answer | Implementiert (aber nicht vollständig genutzt) |

---

## 4. Lücken zwischen Dokumentation und Code

| Anforderung | Dokumentiert | Implementiert | Differenz |
|-------------|:------------:|:------------:|-----------|
| Minimaler Kontext auf Level 1 | Ja | Nein | solution_steps + final_answer immer enthalten |
| Aufgabenspezifische Policy | Ja | Nein | prompt_context_policy nicht genutzt |
| Experimentelle Bedingungen A-E | Ja | Nein | Keine Umschaltmöglichkeit |
| Doppelte Sicherheitsprüfung | Ja | Teilweise | Prüfung vorhanden, aber Werte hart kodertrückt |

---

## 5. Empfohlene Änderungen

### 5.1 ContextOptions nicht hart kodieren

**Statt:**
```python
context_options = ContextOptions(
    include_solution_steps=True,
    include_final_answer=True
)
```

**Besser:**
```python
context_options = ContextOptions()  # Nutzt die Minimal-Defaults
```

### 5.2 ContextOptions-Defaults anpassen (schemas.py)

```python
class ContextOptions(BaseModel):
    include_question_text: bool = True
    include_student_answer: bool = True
    include_diagnosis_code: bool = True
    include_prt_feedback: bool = True
    include_score: bool = False
    include_learning_goals: bool = False
    include_math_rules: bool = False
    include_solution_steps: bool = False  # False als Default!
    include_final_answer: bool = False    # False als Default!
    include_chat_history: bool = True
```

### 5.3 Task-Policy in PromptBuilder einbeziehen

Der PromptBuilder sollte die `prompt_context_policy` aus der Task-JSON
laden und die Werte aus `solution_step_limit_by_hint_level` respektieren.

### 5.4 Kontextbedingungen A-E als Presets

Für Experimente könnten vordefinierte Kontext-Presets eingeführt werden:

```python
CONTEXT_PRESETS = {
    "A": ContextOptions(
        include_question_text=True,
        include_student_answer=True,
        include_diagnosis_code=False,
        include_prt_feedback=False
    ),
    "B": ContextOptions(
        include_question_text=True,
        include_student_answer=True,
        include_diagnosis_code=True,
        include_prt_feedback=False
    ),
    # ...
}
```

---

## 6. Priorisierte Maßnahmen

| Priorität | Maßnahme | Aufwand |
|:---------:|----------|:-------:|
| 1 | ContextOptions-Defaults auf False setzen | Gering |
| 2 | /start verwendet keine hart kodierte ContextOptions | Gering |
| 3 | Task-Policy in PromptBuilder einbeziehen | Mittel |
| 4 | Kontext-Presets für Experimente | Mittel |

---

## 7. Fazit

Die Architektur ist grundsätzlich gut designed - die `ContextOptions` bieten
die nötige Flexibilität. Allerdings wird dieses Potenzial **nicht genutzt**,
weil:

1. Die /start-Route die ContextOptions hart kodiert
2. Die Task-spezifische Policy ignoriert wird
3. Die Defaults zu viel Kontext standardmäßig einschließen

Für die Masterarbeit ist dies besonders relevant, da die **experimentelle
Untersuchung** verschiedener Kontextbedingungen (Forschungsfrage 3) ein
zentrales Element ist.