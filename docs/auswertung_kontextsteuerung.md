# Auswertung: Kontextsteuerung und Erweiterbarkeit

## Aktueller Abgleich: 2026-10-02

**Status: technischer Nachtrag, keine empirischen Modellresultate.** Die
Abschnitte 1-7 darunter sind eine historische Codeanalyse und bleiben als
Arbeitsstand erhalten. Ihre damaligen Zeilenverweise, Defizitbehauptungen und
Aenderungsvorschlaege sind nicht als aktuelle Vorgaben zu verwenden. Der neue
Untersuchungsumfang steht in [eval-protocol-2](evaluation_protocol.md).

### Verfügbarkeit und Sichtbarkeit

`StackContext` kann Referenzschritte und Endloesung enthalten, ohne sie dem LLM
zu zeigen. `PromptBuilder` prueft fuer beide Felder weiterhin Kontextoption
**UND** aktive Stufenfreigabe. Eine eingeschaltete Endloesungsoption reicht auf
einer verbietenden Stufe nicht aus. Ein interner API-Endloesungswert kann zudem
die erlaubte Schrittfolge als Literal-Guard begrenzen. Die alte pauschale
Behauptung, Loesungsdaten wuerden deshalb auf Stufe 1 mitgesendet, ist fuer den
sichtbaren Prompt falsch; Datenpool, Request-Payload und Prompt sind zu trennen.

Die zentrale `HintPolicy` ist die generische Laufzeitquelle. Legacy-Felder
`tutor_policy`, `hint_levels` und `prompt_context_policy` bleiben aus
Schema-/Datenformatgruenden in den Tasks, sind aber kein zweiter aktiver
Eskalationsmechanismus. Die historische Empfehlung, diese Task-Policy wieder
einzubauen, ist keine aktuelle Architekturvorgabe.

### Aktuelle Steuerung

| Ebene | Vorhandene Umsetzung | Empirische Pruefung |
|---|---|---|
| Kontext | Zehn API-Flags und `CONTEXT_OPTIONS`-Defaults | Angeforderte versus effektive Optionen und echte Promptabschnitte |
| Stufe 0 | Diagnosefrage mit eigener `TUTOR_STAGE0_CONTEXT_OPTIONS`-Kappung | Sichtbarer Kontext und Informationsgewinn statt erzwungenem Rechenschritt-Rating |
| Diagnose | `provided`, `model`, `none`; bei `model`/`none` kein gelieferter Code/Feedback | Unabhaengige Hypothese darf das erwartete Label nicht vorher sehen |
| Regeln | Rolle, Stufenziele, erlaubte/verbotene Inhalte, Wortgrenzen, Frage-/Stufenanzeige | Aktive Policy und Konfigurationssnapshot/hash, nicht nur Profilname |
| Generierung | Allowlist-Modell, Temperatur, Tokenlimit, Format, angeforderte Thinking-Steuerung | Konstant halten oder ausdruecklich als Kontrast benennen |
| Start | Gemeinsame feste Baseline oder Modellwahl aus Initialantwort und angeforderten API-Optionen unter Stufe-0-Caps | Auswahlprompt/-optionen separat als `start_selection_context` pruefen; keine globalen HTML-Optionen |
| Dialog | Aktuelle Nachricht auch ohne Historie; passive Zeit-plus-Verwirrung-Anpassung | Identische Skripte/Zeiten, keine automatische Timerantwort |

Die Betriebsdefaults sind keine bereits optimierte Baseline: Start 1, `fixed`,
`provided`, `tutor`, `text`, Adaptation aus. Minimum ist 0, Standardmaximum 4;
andere Grenzen brauchen passende Policies und kompatible Clientlimits.
Tutorregeln duerfen nach empirischer Auswahl geaendert werden, jedoch nicht
innerhalb derselben gepinnten Bedingung.
Die gemeinsame Baseline ist noch manuell anhand vorab festzulegender
Pilotkriterien und konkreter Run-/Attempt-Belege auszuwaehlen. Es ist keine
automatische Optimierungsfunktion implementiert. Die geladene App-Policy
bleibt bis zum Neustart identisch fuer Generierung, Health-Hash und
Konfigurations-GET; letzterer bietet keinen Hot-Swap.

`base` ist Aufgabe plus Antwort unter der jeweiligen Serverpolicy. Es ist
weder die empirisch gewaehlte Startbaseline noch eine allgemeine
Assistentenbedingung. Letztere benoetigt wirklich `TUTOR_POLICY_MODE=general`.
Dann Loesungsanwesenheit weiterhin erfassen, ohne inaktive Tutorverbote als
Regelverstoss anzuwenden.

### Referenzen und Grenzen

Die optionale Task-Struktur `evaluation_examples` bindet 15 konkrete
synthetische Antworten an zwei explizite, zur lokalen `model_solution`
passende Funktionen. Exportstatus und Evidenz bleiben `pending`; die formale
Validierung ist keine mathematische Pruefung. Der erste Vergleich benoetigt
keine PRT-Anbindung. Gelieferte Fehlerlabels, LLM-Hypothesen, unabhaengige
Referenzpruefung und spaetere STACK-Ergebnisse sind getrennte Quellen.
Fehlender Score bleibt `None`, nicht `0.0`.
Der zentrale Payload-Builder setzt synthetische Diagnoseherkunft auch fuer
direkte Taskexports auf den API-Wert `synthetic`; diese Normalisierung aendert
keinen Evidenzstatus. Eine LLM-Hypothese verifiziert weder Fehlerlabel noch Score.

Evaluatoren erhalten gemeinsame Referenzen derselben Instanz auch bei fuer
den Generator ausgeblendeten Task-Feldern. Bei Moodle-Zufallsvarianten werden
feste lokale Beispielreferenzen nicht angehaengt. Variantenkorrektheit
entsteht nicht durch hohe Hilfestufe oder einen passenden Fehlercode.

Die API liefert aktive `hint_policy`, `configuration`, `config_sha256`, echte
`prompt_messages`, effektive Optionen sowie Start-/Adaptationsmetadaten.
Ein lokaler Preview ist keine gemessene Servereingabe. Ohne echten Prompt
bleiben promptbezogene Checks `inconclusive`. Der Prompt-Guard ist kein
vollstaendiger Ausgabefilter und keine symbolische Aequivalenzpruefung;
fehlender Offenlegungstreffer beweist keine Loesungsabwesenheit.

Der optionale Judge verwendet einen anderen gespeicherten Modellalias und
geschuetzten Zugang. Seine Ratings bleiben von Menschenratings getrennt.
Version `judge-rubric-1.0-v2` beruecksichtigt die separate
`diagnosis_hypothesis`, `current_message`, `turn_index` und beobachtete
`generator_rule_settings`; deaktivierte Regeln sind keine angenommenen
Anforderungen. Modellberichte bleiben nach Bedingung/Turn getrennt.

Adaptation verwendet ein monotones Intervall seit erfolgreicher Antwort nur
bei passender Serverprozess-Uhr; nach Neustart oder anderem Worker ist es
unbekannt. Dieses moeglicherweise Leerlauf enthaltende Intervall ist keine aktive Lernzeit.
Ein explizit authentifiziertes Simulationsintervall ist auf 86400 Sekunden
begrenzt und dispatcht ebenso wenig wie ein realer Zeitablauf automatisch
eine LLM-Anfrage. Die Notebookvorbereitung nutzt jetzt `eval-protocol-2`,
ohne daraus eine durchgefuehrte Studie oder optimierte Baseline abzuleiten.
Skriptantworten, auch spaetere korrekte Antworten, sind vorherbestimmt und
belegen weder Lernfortschritt noch Motivation.

### Nächste Untersuchung

1. Referenzpruefung und Entwicklungs-/Held-out-Split dokumentieren, Bloecke A-D
   als einzelne Bedingungen authoren und vor Live-Aufrufen validieren.
2. Stufen 0-4 pilotieren und eine gemeinsame Baseline nach vorab benannten
   Kriterien auswaehlen; erst danach den individuellen Start vergleichen.
3. Wenige Diagnose-, Regel- und Adaptationskontraste getrennt pruefen; echte
   effektive Prompts/Policies vor inhaltlicher Interpretation kontrollieren.
4. Technik, Offenlegungsindikatoren, Menschenratings und optionale
   Modellratings mit getrennten Nennern berichten. Offline-Mocks sind keine
   empirischen Modellantworten.

---

## Historische Analyse

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
