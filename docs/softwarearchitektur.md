# Softwarearchitektur des STACK-LLM-Tutors

## 1. Ziel des Systems

Das Projekt implementiert einen prototypischen KI-Tutor für digitale Mathematikaufgaben in Moodle/STACK.

Die Verantwortlichkeiten sind bewusst getrennt:

- **STACK und PRTs** übernehmen die mathematische Bewertung und Fehlerdiagnose.
- **Der Prompt-Builder** erzeugt aus Aufgabe, Studierendenantwort, Diagnose, Hilfestufe und Chatverlauf einen strukturierten Tutor-Prompt.
- **Das LLM** formuliert einen didaktischen Hinweis.
- **FastAPI** stellt Weboberfläche und REST-API bereit.
- **SQLite** speichert Chat-Sitzungen, Nachrichten und die aktuelle Hilfestufe.

Der grundlegende Datenfluss lautet:

```text
Moodle/STACK
    ↓
Aufgaben-ID, Antwort und PRT-Diagnose
    ↓
FastAPI-Anwendung
    ↓
Aufgaben- und Kontextverwaltung
    ↓
generische Hint-Policy
    ↓
Prompt-Builder
    ↓
LLM-API
    ↓
Tutorhinweis
    ↓
HTML-Webseite oder JSON-Response
```

---

## 2. Projektstruktur

```text
stack-llm-tutor-interface/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── database.py
│   ├── chat_store.py
│   ├── hint_policy.py
│   ├── prompt_builder.py
│   ├── task_loader.py
│   ├── ollama_client.py
│   └── templates/
│       └── tutor_page.html
├── config/
│   └── hint_levels.json
├── data/
│   └── tutor.db
├── schemas/
│   └── stack_ai_tutor_task.schema.json
├── tasks/
│   ├── ableitung_kettenregel_exp_001.json
│   └── ableitung_produktregel_001.json
├── moodle/
├── tests/
├── docs/
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

---

## 3. Zentrale Komponenten

### 3.1 `app/main.py`

`main.py` ist der Einstiegspunkt der FastAPI-Anwendung. Beim Start werden die Datenbank initialisiert, Aufgaben geladen und die generische Hint-Policy bereitgestellt [6].

Die Anwendung stellt folgende Endpunkte bereit:

```text
GET  /health
GET  /tasks
GET  /start
POST /api/tutor/start
POST /api/tutor/{chat_id}/next-hint
POST /api/tutor/{chat_id}/message
GET  /api/tutor/{chat_id}/history
```

#### `GET /health`

Liefert den Zustand der Anwendung:

```json
{
  "status": "ok",
  "tasks_loaded": 2,
  "default_model": "qwen3.6:27b"
}
```

#### `GET /tasks`

Listet die geladenen Aufgaben mit ID, Thema, Unterthema und Status auf.

#### `GET /start`

Dient als Moodle-/STACK-kompatibler Einstiegspunkt. Der Endpunkt erwartet:

```text
qid
diagnosis
ans1
hint_level
model
chat_id
```

Beispiel:

```text
/start?qid=ableitung_kettenregel_exp_001
&diagnosis=missing_inner_derivative
&ans1=-5
&hint_level=1
```

Der Endpunkt:

1. validiert Aufgaben-ID und Diagnosecode
2. lädt die passende Aufgabe
3. erzeugt oder lädt einen Chat
4. erstellt den STACK-Kontext
5. baut den LLM-Prompt
6. ruft das LLM auf
7. speichert die Antwort
8. rendert `tutor_page.html`

#### REST-Endpunkte

Die REST-Endpunkte unterstützen strukturierte JSON-Kommunikation:

- `/api/tutor/start` erzeugt eine neue Tutor-Sitzung
- `/next-hint` erhöht die Hilfestufe
- `/message` sendet eine Rückfrage innerhalb eines bestehenden Chats
- `/history` liefert die gespeicherte Chat-Historie

---

### 3.2 `app/config.py`

`config.py` zentralisiert alle Laufzeit- und Pfadkonfigurationen [3].

Wichtige Pfade:

```text
TASK_DIR
SCHEMA_PATH
TEMPLATE_DIR
HINT_LEVELS_PATH
DATABASE_PATH
```

LLM-Konfiguration:

```text
OLLAMA_BASE_URL
OLLAMA_MODEL
OLLAMA_TIMEOUT
ALLOWED_MODELS
```

Weitere Grenzen:

```text
MAX_STUDENT_ANSWER_LENGTH
MAX_HISTORY_MESSAGES
MAX_HINT_LEVEL
```

Derzeitiges Standardmodell:

```text
qwen3.6:27b
```

Erlaubte Modelle:

```text
qwen3.6:27b
qwen3.8:27b
granite4.1:30b
mistral-medium-3.5:128b
```

`qwen3.6:27b` besitzt 27,8 Milliarden Parameter, Q4_K_M-Quantisierung, ein Kontextfenster von 262.144 Tokens und unterstützt Completion, Tools, Thinking und Vision [1].

---

### 3.3 `app/schemas.py`

`schemas.py` definiert die Pydantic-Modelle für die REST-API [9].

#### `ContextOptions`

Steuert, welche Informationen in den Prompt aufgenommen werden:

```python
include_question_text
include_student_answer
include_diagnosis_code
include_prt_feedback
include_score
include_learning_goals
include_math_rules
include_solution_steps
include_final_answer
include_chat_history
```

Damit können experimentelle Kontextbedingungen erzeugt werden:

```text
A: Aufgabe + Antwort
B: Aufgabe + Antwort + Diagnose
C: Aufgabe + Antwort + Diagnose + PRT-Feedback
D: zusätzlicher Fachkontext
E: zusätzliche Lösungsschritte
```

#### `StackContext`

Repräsentiert den vollständigen Tutor-Kontext:

```text
question_id
question_text
student_answer
diagnosis_code
prt_feedback
score
seed
learning_goals
math_rules
solution_steps
final_answer
```

#### API-Schemas

Weitere Modelle:

```text
TutorRequest
NextHintRequest
UserChatRequest
ChatMessage
TutorResponse
ChatHistoryResponse
```

---

### 3.4 `app/task_loader.py`

`task_loader.py` lädt Aufgaben aus:

```text
tasks/*.json
```

Jede Aufgabe wird gegen folgendes Schema validiert:

```text
schemas/stack_ai_tutor_task.schema.json
```

Der Loader prüft:

- Existenz des Aufgabenverzeichnisses
- Existenz des Schemas
- Gültigkeit jeder Aufgaben-JSON
- Eindeutigkeit der `question_id`
- Vorhandensein mindestens einer Aufgabe

Ungültige Aufgaben verhindern den Start der Anwendung. Dadurch werden Datenfehler früh erkannt [10].

---

### 3.5 Aufgaben-JSON

Die Aufgaben-Dateien enthalten aufgabenspezifische Informationen:

```text
question_id
topic
subtopic
question_text
learning_goals
math_rules
diagnoses
model_solution
```

Beispiel:

```json
{
  "question_id": "ableitung_kettenregel_exp_001",
  "topic": "Differentialrechnung",
  "subtopic": "Kettenregel",
  "question_text": "Differenzieren Sie die Funktion ...",
  "learning_goals": [
    "Die Kettenregel anwenden"
  ],
  "diagnoses": {
    "missing_inner_derivative": {
      "title": "Die innere Ableitung fehlt"
    },
    "unknown_error": {
      "title": "Der Fehler konnte nicht eindeutig bestimmt werden"
    }
  },
  "model_solution": {
    "final_answer": "...",
    "solution_steps": []
  }
}
```

Die Aufgaben-JSON dient als kuratierte Kontext- und Referenzbasis. Die mathematische Aufgabenstellung soll perspektivisch möglichst direkt aus Moodle/STACK übernommen werden.

---

### 3.6 `app/hint_policy.py`

`hint_policy.py` lädt die aufgabenunabhängigen Hilfestufen aus:

```text
config/hint_levels.json
```

Die Policy prüft für jede Hilfestufe folgende Pflichtfelder:

```text
name
goal
max_words
may_include
must_not_include
include_solution_steps
include_final_answer
```

Es müssen alle Stufen von 1 bis `MAX_HINT_LEVEL` definiert sein [5].

Beispielhafte Stufen:

| Level | Bezeichnung | Zweck |
|---:|---|---|
| 1 | Orientierung | Konzept oder Fehlerbereich aktivieren |
| 2 | Strukturierung | Aufgabe in Teilprobleme zerlegen |
| 3 | Nächster Rechenschritt | konkreten Teilschritt ermöglichen |
| 4 | Ausführliche Unterstützung | Lösungsweg ausführlich erläutern |

Die Hilfestufen sind zentral und nicht aufgabenspezifisch.

---

### 3.7 `app/prompt_builder.py`

Der `PromptBuilder` erzeugt eine Liste von Chat-Nachrichten für das LLM [8].

Beispiel:

```python
[
  {
    "role": "system",
    "content": "Tutorrolle und Hint-Policy"
  },
  {
    "role": "assistant",
    "content": "Vorheriger Hinweis"
  },
  {
    "role": "user",
    "content": "Aufgabe, Antwort und Diagnose"
  }
]
```

#### Systemnachricht

Die Systemnachricht enthält:

- Tutorrolle
- STACK als Bewertungsinstanz
- aktuelle Hilfestufe
- Ziel der Hilfestufe
- erlaubte Inhalte
- verbotene Inhalte
- maximale Wortzahl
- Sicherheitsregeln
- Aufforderung zu einer aktivierenden Rückfrage

#### Kontextsteuerung

Die Benutzer-Nachricht wird dynamisch aus `ContextOptions` aufgebaut.

Beispiel:

```text
AUFGABENSTELLUNG:
...

STUDIERENDENANTWORT:
<student_answer>
...
</student_answer>

PRT-DIAGNOSECODE:
...

PRT-FEEDBACK:
...
```

#### Schutz vor Lösungsverrat

Lösungsschritte werden nur aufgenommen, wenn beide Bedingungen erfüllt sind:

```text
ContextOptions.include_solution_steps = true
Hint-Policy.include_solution_steps = true
```

Die Endlösung wird nur aufgenommen, wenn beide Bedingungen erfüllt sind:

```text
ContextOptions.include_final_answer = true
Hint-Policy.include_final_answer = true
```

Dadurch kann beispielsweise eine Request-Option die Endlösung auf Level 1 nicht eigenständig freigeben.

---

### 3.8 `app/database.py`

`database.py` initialisiert eine SQLite-Datenbank unter:

```text
data/tutor.db
```

Tabellen:

#### `chats`

```text
chat_id
question_id
stack_context_json
current_hint_level
created_at
updated_at
```

#### `messages`

```text
message_id
chat_id
role
content
created_at
```

Zwischen `messages` und `chats` besteht eine Fremdschlüsselbeziehung mit `ON DELETE CASCADE` [4].

---

### 3.9 `app/chat_store.py`

`ChatStore` kapselt den SQLite-Zugriff für Chat-Sitzungen [2].

Unterstützte Funktionen:

```text
create_chat
get_chat
add_message
get_messages
set_hint_level
next_hint_level
```

Jeder neue Chat erhält eine UUID:

```python
chat_id = str(uuid4())
```

Die UUID wird vor Zugriffen validiert.

Die Hilfestufe wird begrenzt:

```python
next_level = min(
    current_hint_level + 1,
    MAX_HINT_LEVEL
)
```

Auf diese Weise bleibt Level 4 die höchste Stufe.

---

### 3.10 `app/ollama_client.py`

`ollama_client.py` kapselt die Kommunikation mit einer nativen Ollama-API [7].

Unterstützte Funktionen:

```text
call_ollama_chat
call_ollama_generate
call_ollama
```

Native Ollama-Endpunkte:

```text
POST /api/chat
POST /api/generate
```

Chat-Payload:

```json
{
  "model": "qwen3.6:27b",
  "messages": [],
  "stream": false,
  "think": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 400
  }
}
```

Der Client unterstützt:

- TLS-Zertifikatsprüfung
- Timeouts
- HTTP-Fehlerbehandlung
- Verbindungsfehler
- JSON-Validierung
- Prüfung auf leere Antworten
- Erkennung reiner Thinking-Ausgaben

---

## 4. Datenfluss eines neuen Tutoraufrufs

```text
1. Moodle/STACK öffnet GET /start
2. FastAPI validiert qid, diagnosis und ans1
3. task_loader liefert die passende Aufgabe
4. main.py erzeugt einen StackContext
5. ChatStore erzeugt eine UUID und speichert den Kontext
6. HintPolicy liefert die aktuelle generische Hilfestufe
7. PromptBuilder erzeugt System- und User-Nachricht
8. Der LLM-Client sendet den Request an das Modell
9. Die Tutorantwort wird in SQLite gespeichert
10. Das Jinja2-Template zeigt den Hinweis an
```

---

## 5. Datenfluss für einen weiteren Hinweis

```text
1. Benutzer klickt auf „Weiterer Hinweis“
2. Der bestehende Chat wird über chat_id geladen
3. ChatStore erhöht current_hint_level
4. HintPolicy liefert die Regeln der neuen Stufe
5. PromptBuilder integriert die Chat-Historie
6. Lösungskontext wird abhängig von der Stufe freigegeben
7. Das LLM generiert einen neuen Hinweis
8. Der Hinweis wird gespeichert und zurückgegeben
```

---

## 6. Datenfluss einer Chat-Nachricht

```text
1. Benutzer sendet eine Rückfrage
2. POST /api/tutor/{chat_id}/message
3. Die User-Nachricht wird in SQLite gespeichert
4. Die aktuelle Hilfestufe bleibt bestehen
5. Die letzten Nachrichten werden geladen
6. PromptBuilder ergänzt die Historie
7. Das LLM erzeugt eine Antwort
8. Die Assistant-Nachricht wird gespeichert
```

---

## 7. LLM-Infrastruktur

### 7.1 Dokumentierter Hochschuldienst

Dokumentierte Basis-URL:

```text
https://f2ki-h100-1.f2.htw-berlin.de:11435
```

Dokumentierte native Ollama-Endpunkte:

```text
GET  /api/tags
POST /api/chat
POST /api/generate
```

### 7.2 Beobachteter Dienst

Die Basis-URL zeigt aktuell die OpenAPI-Dokumentation eines LiteLLM-Proxys.

Testergebnisse:

| Endpunkt | Status | Bedeutung |
|---|---:|---|
| `GET /api/tags` | 404 | native Ollama-Route nicht registriert |
| `POST /api/chat` | 404 | native Ollama-Route nicht registriert |
| `POST /v1/chat/completions` | 401 | LiteLLM erreichbar, API-Key erforderlich |

Die aktuelle Implementierung verwendet weiterhin das native Ollama-Format [7]. Für den Hochschuldienst ist daher entweder:

- eine gültige native Ollama-Adresse
- oder ein LiteLLM-API-Key mit OpenAI-kompatiblem Client

erforderlich.

---

## 8. Empfohlene Weiterentwicklung der LLM-Schicht

Die Modellkommunikation sollte backendunabhängig abstrahiert werden:

```text
app/llm/
├── base.py
├── ollama.py
├── litellm.py
└── factory.py
```

Zielschnittstelle:

```python
class LLMClient:
    def chat(
        self,
        messages,
        model,
        temperature,
        max_tokens
    ) -> str:
        raise NotImplementedError
```

Adapter:

```text
OllamaClient
    → POST /api/chat

LiteLLMClient
    → POST /v1/chat/completions
    → Authorization: Bearer API_KEY
```

Auswahl über Umgebungsvariablen:

```dotenv
LLM_API_MODE=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:8b
```

oder:

```dotenv
LLM_API_MODE=litellm
LLM_BASE_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435
LLM_API_KEY=...
LLM_MODEL=qwen3.6:27b
```

---

## 9. Sicherheitsarchitektur

### Studierendenantworten

Studierendenantworten gelten als nicht vertrauenswürdig.

Maßnahmen:

- maximale Länge begrenzen
- nicht als Systemprompt verwenden
- in separaten Tags kennzeichnen
- Anweisungen aus der Antwort ausdrücklich ignorieren
- HTML-Ausgabe durch Jinja2 escapen
- keine personenbezogenen Daten übertragen

### Modell-Allowlist

Das Modell darf nicht beliebig über den URL-Parameter ausgewählt werden.

Die erlaubten Modelle stehen zentral in `config.py` [3].

### API-Schlüssel

API-Schlüssel dürfen nicht im Repository gespeichert werden.

Geeignete Speicherorte:

```text
Umgebungsvariable
.env außerhalb der Versionsverwaltung
Docker Secret
n8n Credential
Secret Store
```

### TLS

Die Zertifikatsprüfung bleibt aktiviert:

```python
verify=True
```

---

## 10. Testarchitektur

Empfohlene Teststruktur:

```text
tests/
├── test_hint_policy.py
├── test_prompt_builder.py
├── test_context_options.py
├── test_solution_disclosure.py
├── test_chat_store.py
├── test_task_loader.py
├── test_api.py
├── test_ollama_integration.py
└── test_llm_regression.py
```

### Unit-Tests

Ohne externen LLM-Dienst:

- alle Hilfestufen vorhanden
- ungültige Hilfestufen werden abgelehnt
- Kontextfelder lassen sich deaktivieren
- Lösungsschritte bleiben auf niedrigen Levels verborgen
- Endlösung erscheint erst auf freigegebener Stufe
- UUIDs werden korrekt erzeugt und validiert
- Nachrichten werden in korrekter Reihenfolge gespeichert
- Aufgaben-JSONs entsprechen dem Schema

### Integrationstests

Mit externen Diensten:

- LLM-Endpunkt erreichbar
- Modellalias gültig
- Chat-Request erfolgreich
- Antwort nicht leer
- Timeouts werden behandelt
- Authentifizierungsfehler werden erkannt

### Regressionstests

Für einen festen Satz von Aufgaben und Fehlerantworten:

- Hinweis enthält keine mathematisch falsche Aussage
- Hinweis passt zur PRT-Diagnose
- Hinweis entspricht der Hilfestufe
- Endlösung wird nicht zu früh verraten
- Wortgrenze wird eingehalten
- Ausgabe enthält keine internen Promptbestandteile

---

## 11. Reproduzierbarkeit

Für jeden Evaluationslauf sollten gespeichert werden:

```text
question_id
student_answer
diagnosis_code
prt_feedback
hint_level
context_options
chat_id
model
API-Backend
Prompt-Version
temperature
max_tokens
generierter Hinweis
Antwortzeit
HTTP-Status
Zeitstempel
```

Zusätzlich sollte die verwendete Modellversion bzw. der Digest dokumentiert werden. Für `qwen3.6:27b` ist im bereitgestellten Modellbestand der Digest `a50eda8ed977ab48a12431878896b27ffd5cef552c17af3317d9623b939a7f1e` angegeben [1].

---

## 12. Aktueller Entwicklungsstand

Bereits implementiert:

- FastAPI-Anwendung
- Moodle-kompatibler `/start`-Endpunkt
- strukturierte REST-Endpunkte
- Aufgaben-Loader
- JSON-Schema-Validierung
- generische Hilfestufen
- parametrisierbarer Prompt-Builder
- Chat-Historie mit UUID
- SQLite-Datenbank
- native Ollama-Client-Schnittstelle
- Modell-Allowlist

Noch offen:

- Klärung des HTW-API-Zugangs
- backendunabhängiger LLM-Client
- LiteLLM-Adapter
- vollständige Web-Chat-Oberfläche
- Übernahme der Aufgabenstellung direkt aus Moodle/STACK
- Integration der STACK-API für `/render`, `/validate` und `/grade`
- automatisierte Unit-, Integrations- und Regressionstests
- Logging der Evaluationsmetriken
- Prüfung von LLM-Ausgaben auf Lösungsverrat

---

## 13. Priorisierte nächste Schritte

1. **HTW-Zugang klären**
   - LiteLLM-Key oder korrekte native Ollama-Adresse anfordern

2. **LLM-Client abstrahieren**
   - Ollama- und LiteLLM-Adapter implementieren

3. **Tests ergänzen**
   - Hint-Policy
   - Prompt-Builder
   - Chat-Store
   - Lösungsverrat

4. **Webseite erweitern**
   - Chat-Eingabefeld
   - Chat-Historie
   - Button für weitere Hilfestufe

5. **STACK-Kontext erweitern**
   - Aufgabenstellung aus STACK übernehmen
   - PRT-Feedback und Score übertragen
   - später STACK-API integrieren

6. **Evaluationsdatensatz erstellen**
   - Beispielaufgaben
   - korrekte Antworten
   - typische Fehlerantworten
   - erwartete PRT-Diagnosen

---

## 14. Leitlinien für weitere Änderungen durch OpenCode

Bei Änderungen am Projekt sollten folgende Regeln eingehalten werden:

- Python 3.9 kompatibel bleiben
- `Optional[T]` statt `T | None` verwenden
- bestehende REST-Endpunkte nicht ohne Migration entfernen
- `/start` als Moodle-Adapter erhalten
- Hilfestufen ausschließlich zentral definieren
- Aufgabeninformationen und Tutor-Policy trennen
- Lösungsschritte nur bei entsprechender Hint-Policy freigeben
- Endlösung nur auf ausdrücklich erlaubter Stufe übermitteln
- Chat-Historie ausschließlich serverseitig speichern
- API-Schlüssel niemals hardcodieren
- externe Dienste in Unit-Tests mocken
- Integrationstests mit `pytest.mark.integration` markieren
- LLM-Backend über Konfiguration austauschbar halten
- mathematische Bewertung nicht dem LLM übertragen
- STACK- und PRT-Ergebnisse als maßgebliche Diagnose behandeln