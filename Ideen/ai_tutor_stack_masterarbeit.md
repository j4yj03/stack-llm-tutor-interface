# AI Tutor für Moodle-STACK-Aufgaben

## Arbeitstitel

**Entwicklung eines KI-gestützten Tutors für Moodle-STACK-Aufgaben in mathematischen Grundlagenmodulen**

Alternativ technischer formuliert:

**Prototypische Anbindung eines lokalen LLM-basierten AI Tutors an STACK-Aufgaben über strukturierte Feedback-Daten**

---

## 1. Grundidee

Ziel ist die prototypische Entwicklung eines AI Tutors für digitale Mathematikaufgaben in Moodle/STACK. Dabei soll STACK weiterhin die mathematische Bewertung übernehmen, während der AI Tutor adaptive, didaktisch sinnvolle Hilfestellungen generiert.

Die zentrale Idee lautet:

> **STACK bewertet die mathematische Antwort. Der AI Tutor erklärt, gibt adaptive Hinweise und unterstützt den Lernprozess.**

Die Moodle-Instanz soll im ersten Schritt nicht verändert werden. Stattdessen werden ausgewählte STACK-Aufgaben so angereichert, dass im Feedback ein Link zum AI Tutor angezeigt wird. Dieser Link überträgt ausgewählte Informationen an einen externen AI-Tutor-Server.

---

## 2. Geplantes Minimalsetting

Das geplante Minimalsetting besteht aus folgenden Komponenten:

```text
STACK-Aufgabe in Moodle
        ↓
Studierende geben Antwort ein, z. B. ans1
        ↓
STACK/PRT bewertet die Antwort
        ↓
Feedback enthält Link „AI Tutor“
        ↓
Link übergibt:
    question_id
    diagnosis / Fehlercode
    ans1, URL-kodiert
        ↓
AI-Tutor-Server lädt passende Aufgabendaten
        ↓
lokales LLM erzeugt adaptive Hilfe
```

Die eigentlichen Aufgabendaten liegen als Duplikate auf dem AI-Server, zum Beispiel:

```text
question_id
Aufgabentext
Thema
Lernziel
Musterlösung
typische Fehler
Tutor-Regeln
Hilfestufen
```

Die Studierendenantwort wird dynamisch aus STACK übergeben, zum Beispiel als URL-kodierter Wert von `ans1`.

---

## 3. Erste technische Umsetzungsmöglichkeit

### 3.1 Auswahl eines kleinen Themenbereichs

Für den Prototyp sollte der mathematische Umfang bewusst begrenzt werden. Geeignete Themenbereiche sind beispielsweise:

- Ableitungen
- Produktregel
- Kettenregel
- lineare Gleichungen
- Bruchgleichungen
- komplexe Zahlen

Ein guter Einstieg wäre das Thema **Ableitungen**, da hier typische Fehler gut identifizierbar sind und STACK diese mathematisch prüfen kann.

Beispielaufgabe:

```text
Bestimmen Sie die Ableitung von f(x)=x^2 sin(x).
```

Typische Fehler wären:

```text
Produktregel nicht angewendet
ein Summand der Produktregel fehlt
Ableitung von sin(x) falsch
Ableitung von x^2 falsch
nur ein Faktor wurde abgeleitet
```

---

### 3.2 Anreicherung der STACK-Aufgabe

Die STACK-Aufgabe erhält zusätzliche Tutor-Metadaten, zum Beispiel in den Question Variables oder als fest definierte Informationen:

```maxima
tutor_qid : "ableitung_produktregel_001";
tutor_topic : "Ableitungen";
tutor_subtopic : "Produktregel";
tutor_learning_goal : "Produktregel auf ein Produkt zweier Funktionen anwenden";
```

Im Potential Response Tree werden Fehlerfälle unterschieden. Zu jedem relevanten Fehlerfall wird ein Diagnosecode festgelegt, zum Beispiel:

```text
missing_product_rule_term
wrong_derivative_sin
wrong_derivative_power
syntax_error
unknown_error
```

Das normale STACK-Feedback kann weiterhin angezeigt werden. Zusätzlich erscheint ein Link:

```html
<a target="_blank"
   href="https://ai-tutor.htw.example/start?qid=ableitung_produktregel_001&diagnosis=missing_product_rule_term&ans1={@tutor_ans1@}">
   AI Tutor
</a>
```

---

### 3.3 Basis-URL-Encoding in STACK/Maxima

Damit die Antwort `ans1` sauber in der URL übertragen wird, kann eine einfache Encoding-Funktion definiert werden.

Schematisch:

```maxima
urlencode_basic(s) := block(
  [r],
  r : string(s),
  r : ssubst("%25", "%", r),
  r : ssubst("%20", " ", r),
  r : ssubst("%2B", "+", r),
  r : ssubst("%26", "&", r),
  r : ssubst("%3D", "=", r),
  r : ssubst("%2F", "/", r),
  r : ssubst("%5E", "^", r),
  r : ssubst("%28", "(", r),
  r : ssubst("%29", ")", r),
  r : ssubst("%2A", "*", r),
  r
)$

tutor_ans1 : urlencode_basic(ans1);
```

Dann wird `tutor_ans1` im Feedback-Link verwendet:

```html
<a target="_blank"
   href="https://ai-tutor.htw.example/start?qid=ableitung_produktregel_001&diagnosis=missing_product_rule_term&ans1={@tutor_ans1@}">
   AI Tutor
</a>
```

Für einen ersten Prototyp ist dieses Basis-Encoding ausreichend. Später könnte die Architektur auf Token, serverseitige Speicherung oder POST-Requests umgestellt werden.

---

### 3.4 Aufgaben-Duplikate auf dem AI-Server

Der AI-Server besitzt eine kleine Aufgaben-Datenbank, zum Beispiel als JSON-Dateien:

```json
{
  "question_id": "ableitung_produktregel_001",
  "topic": "Ableitungen",
  "subtopic": "Produktregel",
  "question_text": "Bestimmen Sie die Ableitung von f(x)=x^2 sin(x).",
  "model_answer": "2*x*sin(x)+x^2*cos(x)",
  "learning_goal": "Die Produktregel auf ein Produkt zweier Funktionen anwenden.",
  "typical_errors": {
    "missing_product_rule_term": "Ein Summand der Produktregel fehlt.",
    "wrong_derivative_sin": "Die Ableitung von sin(x) wurde falsch verwendet.",
    "wrong_derivative_power": "Die Potenzregel wurde falsch angewendet.",
    "unknown_error": "Der Fehler konnte nicht eindeutig klassifiziert werden."
  },
  "tutor_policy": {
    "language": "de",
    "do_not_give_final_answer_on_first_hint": true,
    "max_hint_length": 100,
    "tone": "freundlich, fachlich präzise, unterstützend"
  }
}
```

Der Link liefert nur die dynamischen Daten:

```text
qid
diagnosis
ans1
```

Der AI-Server ergänzt daraus den vollständigen Kontext:

```json
{
  "question_id": "ableitung_produktregel_001",
  "student_answer": "2*x*cos(x)",
  "diagnosis": "missing_product_rule_term",
  "question_text": "Bestimmen Sie die Ableitung von f(x)=x^2 sin(x).",
  "learning_goal": "Die Produktregel anwenden",
  "model_answer": "2*x*sin(x)+x^2*cos(x)",
  "policy": {
    "do_not_give_final_answer": true,
    "hint_level": 1
  }
}
```

---

### 3.5 AI-Tutor-Server

Der AI-Tutor-Server kann prototypisch mit Python/FastAPI umgesetzt werden.

Ablauf:

```text
GET /start?qid=...&diagnosis=...&ans1=...
        ↓
Parameter dekodieren
        ↓
Aufgaben-JSON anhand qid laden
        ↓
Prompt erzeugen
        ↓
lokales Modell über Ollama-API aufrufen
        ↓
Tutorantwort anzeigen
```

Schematischer Prompt:

```text
Du bist ein Mathematik-Tutor für Studierende der Ingenieurwissenschaften.

Die Aufgabe lautet:
Bestimmen Sie die Ableitung von f(x)=x^2 sin(x).

Die Studierendenantwort ist:
2*x*cos(x)

STACK hat folgende Diagnose geliefert:
Ein Summand der Produktregel fehlt.

Gib einen kurzen hilfreichen Hinweis.
Gib nicht die vollständige Lösung aus.
Formuliere auf Deutsch.
Stelle möglichst eine aktivierende Rückfrage.
```

Mögliche Tutorantwort:

```text
Du hast bereits erkannt, dass ein Produkt vorliegt. Prüfe noch einmal die Produktregel: Welche zwei Summanden entstehen, wenn beide Faktoren berücksichtigt werden?
```

Damit übernimmt der Tutor nicht die Bewertung, sondern unterstützt den Lernprozess.

---

## 4. Rolle der lokalen Modelle der KI-Werkstatt

Da die KI-Werkstatt über zwei Nvidia H100 GPUs und eine Ollama-API verfügt, kann der Tutor ohne externe Cloud-LLMs betrieben werden.

Das ist aus mehreren Gründen attraktiv:

- Datenschutz
- Kontrolle über Modelle
- geringere Abhängigkeit von externen Anbietern
- gute Einbindung in Hochschulinfrastruktur
- experimenteller Vergleich mehrerer Modelle

Für die prototypische Umsetzung bieten sich insbesondere an:

```text
Qwen3 30B/32B
DeepSeek-R1 32B oder 70B
LLaMA 3.x 70B
Gemma3 als kleineres Vergleichsmodell
```

Eine sinnvolle Rollenverteilung wäre:

```text
Qwen3:
    Hauptmodell für kurze didaktische Tutorantworten

DeepSeek-R1:
    Vergleichsmodell für mathematisch anspruchsvollere Fehleranalysen

LLaMA 70B:
    Vergleichsmodell für sprachlich gute deutschsprachige Erklärungen
```

Für den ersten Prototyp bietet sich ein Start mit **Qwen3 30B/32B** an. Anschließend kann ein Vergleich mit **DeepSeek-R1 32B/70B** durchgeführt werden.

---

## 5. Wissenschaftliche Fragestellungen

Das Thema ist wissenschaftlich interessant, weil es nicht nur um die technische Anbindung eines Chatbots geht. Im Zentrum steht die Frage, wie eine symbolisch-mathematische Bewertungsumgebung wie STACK mit einem generativen KI-Tutor sinnvoll kombiniert werden kann.

### Forschungsfrage 1: Qualität der Tutorhinweise

**Wie gut sind die von lokalen LLMs erzeugten Hinweise auf Basis von STACK-Diagnosedaten?**

Bewertungskriterien:

- fachliche Korrektheit
- didaktische Angemessenheit
- sprachliche Verständlichkeit
- Kürze und Präzision
- Anpassung an den konkreten Fehler

Mögliche Hypothese:

> Durch die Übergabe strukturierter STACK-Diagnosen erzeugt das LLM fachlich zuverlässigere und didaktisch passendere Hinweise als bei Übergabe der Aufgabe und Antwort allein.

---

### Forschungsfrage 2: Lösungsverrat

Ein zentrales didaktisches Problem besteht darin, dass LLMs häufig zu viel verraten.

Daher ergibt sich die Frage:

**Wie zuverlässig kann der AI Tutor daran gehindert werden, vollständige Lösungen auszugeben?**

Bewertungskriterien:

- enthält keine Endlösung
- gibt nur nächsten Schritt
- stellt aktivierende Rückfrage
- verweist auf Konzept statt Ergebnis
- passt zur Hilfestufe

Vergleichbare Prompt-Strategien:

```text
einfacher Prompt
Prompt mit expliziter Tutor-Policy
Prompt mit Hint-Level
Prompt mit Verbot der Musterlösung
Prompt ohne Musterlösung im Kontext
```

Eine wichtige experimentelle Frage wäre:

> Sollte der Tutor die Musterlösung überhaupt erhalten, oder reicht STACK-Diagnose plus Lernziel?

---

### Forschungsfrage 3: Nutzen von STACK-Diagnosen

Hier liegt ein zentraler wissenschaftlicher Kern der Arbeit.

**Verbessern strukturierte PRT-Diagnosecodes die Qualität der KI-generierten Hinweise?**

Man könnte drei Bedingungen vergleichen:

```text
A: LLM bekommt nur Aufgabe + Studierendenantwort
B: LLM bekommt Aufgabe + Studierendenantwort + normales STACK-Feedback
C: LLM bekommt Aufgabe + Studierendenantwort + strukturierten Diagnosecode
```

Zu erwarten wäre:

```text
C liefert die gezieltesten Hinweise.
B ist besser als A.
A ist anfälliger für falsche Fehlerinterpretationen.
```

---

### Forschungsfrage 4: Vergleich lokaler LLMs

Da mehrere lokale Modelle zur Verfügung stehen, bietet sich eine Modell-Evaluation an.

**Welche lokalen LLMs eignen sich am besten als AI Tutor für STACK-Aufgaben?**

Vergleichbare Modelle:

```text
Qwen3
DeepSeek-R1
LLaMA 70B
Gemma3
```

Mögliche Metriken:

- fachliche Korrektheit
- didaktische Qualität
- Antwortzeit
- Deutschqualität
- Befolgung der Tutor-Policy
- Robustheit bei fehlerhaften Eingaben

---

### Forschungsfrage 5: Technische Machbarkeit ohne Moodle-Anpassung

Da der erste Prototyp ohne Änderung der Moodle-Instanz auskommen soll, ist auch die Architektur selbst Forschungsgegenstand.

**Wie weit kommt man mit einer rein aufgabenbasierten Integration über STACK-Feedback-Links?**

Untersucht werden können:

- Welche Daten lassen sich zuverlässig aus STACK heraus übergeben?
- Wie robust ist die URL-Encoding-Lösung?
- Welche Antworttypen verursachen Probleme?
- Wie gut lassen sich Aufgaben-Duplikate auf dem AI-Server pflegen?
- Wo liegen Grenzen dieser Architektur?

Diese Frage ist wichtig, weil sie die spätere Weiterentwicklung vorbereitet.

---

## 6. Mögliche Evaluation

Eine realistische Evaluation könnte auf drei Ebenen erfolgen.

### 6.1 Technische Evaluation

Zu prüfen sind unter anderem:

- Funktioniert die dynamische Übergabe von `ans1`?
- Funktioniert das URL-Encoding?
- Werden verschiedene mathematische Eingaben korrekt übertragen?
- Kann der AI-Server die passende `question_id` auflösen?
- Wie stabil ist der Ollama-Aufruf?
- Wie lang sind die Antwortzeiten?

Mögliche Testfälle:

```text
2*x*cos(x)
x^2+3*x
(x+1)/(x-2)
sqrt(x+1)
sin(x^2)
```

---

### 6.2 Fachlich-didaktische Expertenevaluation

Mehrere Tutorantworten werden durch Lehrende bewertet.

Kriterien auf einer Skala von 1 bis 5 könnten sein:

- fachlich korrekt
- hilfreich
- verständlich
- nicht zu lösungsverratend
- passend zum Fehler
- sprachlich angemessen

---

### 6.3 Kleine Studierendenstudie

Optional könnte eine kleine Pilotstudie durchgeführt werden.

Möglicher Vergleich:

```text
Gruppe A: normales STACK-Feedback
Gruppe B: STACK-Feedback + AI Tutor
```

Untersucht werden könnte:

- Bearbeitungserfolg
- Anzahl weiterer Versuche
- subjektive Nützlichkeit
- Verständnis des Fehlers
- Akzeptanz des Tutors

Für eine Masterarbeit reicht jedoch auch eine Kombination aus technischer Evaluation und Expert Review.

---

## 7. Konkrete erste Meilensteine

### Meilenstein 1: Aufgabenformat definieren

Ein einfaches JSON-Schema für Aufgaben auf dem AI-Server:

```json
{
  "question_id": "...",
  "topic": "...",
  "question_text": "...",
  "model_answer": "...",
  "learning_goal": "...",
  "typical_errors": {},
  "tutor_policy": {}
}
```

### Meilenstein 2: Eine STACK-Aufgabe anreichern

Eine erste Aufgabe bekommt:

```text
question_id
diagnosis code im PRT
urlencode_basic für ans1
AI-Tutor-Link im Feedback
```

### Meilenstein 3: AI-Tutor-Server bauen

Minimaler Funktionsumfang:

```text
FastAPI-Endpunkt /start
Parameter qid, diagnosis, ans1
Aufgaben-JSON laden
Ollama-API aufrufen
Antwort als Webseite anzeigen
```

### Meilenstein 4: Modelltest

Vergleich von mindestens zwei Modellen, zum Beispiel:

```text
Qwen3
DeepSeek-R1
```

### Meilenstein 5: Evaluation

Bewertung von etwa 10 bis 20 Aufgaben-/Fehlerkombinationen anhand eines Kriterienrasters.

---

## 8. Grenzen des ersten Prototyps

Die vorgeschlagene Lösung ist bewusst einfach. Sie hat Grenzen:

- Die Daten stehen in der URL.
- URL-Längen können problematisch werden.
- Basis-URL-Encoding ist nicht vollständig robust.
- Die Aufgaben müssen auf dem AI-Server dupliziert werden.
- Studierendenantworten können manipuliert werden.
- Es gibt noch keine serverseitige Zugriffskontrolle.

Für eine Masterarbeit ist das kein Nachteil, sondern ein wichtiger Diskussionspunkt. Die Arbeit kann klar zwischen Prototyp und produktiver Zielarchitektur unterscheiden.

Mögliche produktive Weiterentwicklungen:

- Token statt URL-Daten
- Moodle-Plugin
- serverseitiges Speichern des Tutor-Kontexts
- POST statt GET
- bessere Datenschutzmechanismen
- Logging und Learning Analytics
- Integration in Moodle-UI

---

## 9. Kernaussage

Das geplante Setting ist technisch realistisch, didaktisch sinnvoll und wissenschaftlich gut untersuchbar.

> STACK liefert die mathematische Bewertung und Diagnose. Der AI Tutor nutzt diese Diagnose, die Studierendenantwort und eine Aufgabenbeschreibung, um adaptive, deutschsprachige Hilfen zu erzeugen.

Die prototypische Anbindung erfolgt zunächst ohne Moodle-Änderung über einen Feedback-Link mit:

```text
question_id
Diagnosecode
URL-kodierter Antwort ans1
```

Die eigentlichen Aufgabendaten liegen dupliziert auf dem AI-Server und werden dort mit einem lokalen LLM der KI-Werkstatt verarbeitet.

