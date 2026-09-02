# Integration des HTW-LLM-Dienstes in den STACK-LLM-Tutor

## 1. Zielsetzung

Ziel ist die Anbindung eines selbst gehosteten Sprachmodells der HTW Berlin an den FastAPI-basierten STACK-LLM-Tutor.

Der Tutor soll folgende Verarbeitungskette realisieren:

```text
Moodle/STACK
    ↓
Aufgaben-ID, Aufgabenstellung, Studierendenantwort und PRT-Diagnose
    ↓
FastAPI-Tutor-Backend
    ↓
Prompt-Builder mit generischen Hilfestufen
    ↓
HTW-LLM-Dienst
    ↓
Didaktischer Tutorhinweis
    ↓
Tutor-Webseite und Chat-Historie
```

Die mathematische Bewertung soll nicht durch das LLM erfolgen. STACK und die Potential Response Trees bleiben die maßgebliche Bewertungs- und Diagnoseinstanz.

---

## 2. Aktuelle Projektstruktur

Die empfohlene Projektstruktur lautet:

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
├── moodle/
│   ├── question.xml
│   └── stack_link_example.html
├── schemas/
│   └── stack_ai_tutor_task.schema.json
├── tasks/
│   ├── ableitung_kettenregel_exp_001.json
│   └── ableitung_produktregel_001.json
├── tests/
│   ├── __init__.py
│   ├── test_endpoint.py
│   ├── test_ollama_integration.py
│   ├── test_prompt_builder.py
│   ├── test_hint_policy.py
│   ├── test_chat_store.py
│   └── test_solution_disclosure.py
├── docs/
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 3. Aufgaben der Module

### 3.1 `main.py`

`main.py` enthält:

- die FastAPI-Anwendung
- den Moodle-kompatiblen Endpunkt `/start`
- die Chat-API
- die Auswahl des Sprachmodells
- die Erzeugung und Speicherung von Chats
- den Aufruf des Prompt-Builders
- den Aufruf des LLM-Clients
- die Ausgabe über ein Jinja2-Template

Aktuell werden unter anderem folgende Endpunkte bereitgestellt:

```text
GET  /health
GET  /tasks
GET  /start
POST /api/tutor/start
POST /api/tutor/{chat_id}/next-hint
POST /api/tutor/{chat_id}/message
GET  /api/tutor/{chat_id}/history
```

---

### 3.2 `task_loader.py`

`task_loader.py` lädt die Aufgaben-JSON-Dateien aus:

```text
tasks/
```

Jede Aufgabe wird beim Start gegen folgendes Schema geprüft:

```text
schemas/stack_ai_tutor_task.schema.json
```

Dabei werden unter anderem geprüft:

- erforderliche Eigenschaften
- Datentypen
- Diagnosecodes
- Musterlösung
- Aufgaben-ID
- Lernziele
- zusätzliche Tutor-Metadaten

Mögliche Probleme:

- fehlende Pflichtfelder
- doppelte `question_id`
- ungültige Datentypen
- Aufgaben-JSON entspricht noch einem älteren Schema
- generische Hilfestufen liegen gleichzeitig in Aufgaben-JSON und zentraler Konfiguration

---

### 3.3 `hint_policy.py`

`hint_policy.py` lädt die generischen Hilfestufen aus:

```text
config/hint_levels.json
```

Die Hilfestufen sind aufgabenunabhängig und gelten zentral für alle Aufgaben.

Beispiel:

```text
Level 1: Orientierung
Level 2: Strukturierung
Level 3: nächster Rechenschritt
Level 4: ausführliche Unterstützung
```

Die Policy prüft beim Start, ob alle erforderlichen Felder vorhanden sind:

```text
name
goal
max_words
may_include
must_not_include
include_solution_steps
include_final_answer
```

Mögliche Probleme:

- `hint_levels.json` wurde nicht erstellt
- der Dateipfad ist falsch
- eine Hilfestufe fehlt
- ein Pflichtfeld fehlt
- die Aufgaben-JSON enthält noch aufgabenspezifische Hilfestufen, die vom neuen Prompt-Builder nicht mehr genutzt werden

---

### 3.4 `prompt_builder.py`

Der Prompt-Builder erstellt eine Chat-Nachrichtenliste:

```python
[
    {
        "role": "system",
        "content": "..."
    },
    {
        "role": "user",
        "content": "..."
    }
]
```

Der Systemprompt enthält:

- Rolle des Tutors
- aktuelle Hilfestufe
- Ziel der Hilfestufe
- erlaubte Inhalte
- verbotene Inhalte
- maximale Wortzahl
- Sicherheitsregeln
- Verbot der eigenständigen Neubewertung
- Verbot der Befolgung von Anweisungen aus der Studierendenantwort

Der User-Prompt kann abhängig von `ContextOptions` enthalten:

```text
Aufgabenstellung
Studierendenantwort
Diagnosecode
PRT-Feedback
STACK-Score
Lernziele
mathematische Regeln
Lösungsschritte
Musterlösung
Chat-Historie
```

Die Kontextfelder können einzeln ein- oder ausgeschaltet werden.

Beispiel:

```python
ContextOptions(
    include_question_text=True,
    include_student_answer=True,
    include_diagnosis_code=True,
    include_prt_feedback=True,
    include_score=False,
    include_learning_goals=False,
    include_math_rules=False,
    include_solution_steps=True,
    include_final_answer=True,
    include_chat_history=True
)
```

Wichtig ist die doppelte Zugriffskontrolle für Lösungsschritte und Endlösung:

```text
Kontextoption erlaubt die Information
UND
aktuelle Hilfestufe erlaubt die Information
```

Dadurch führt beispielsweise:

```python
include_final_answer=True
```

bei Hilfestufe 1 nicht automatisch dazu, dass die Musterlösung in den Prompt aufgenommen wird.

---

### 3.5 `database.py`

`database.py` initialisiert eine SQLite-Datenbank:

```text
data/tutor.db
```

Die Datenbank enthält die Tabellen:

```text
chats
messages
```

In `chats` werden gespeichert:

- Chat-UUID
- Aufgaben-ID
- serialisierter STACK-Kontext
- aktuelle Hilfestufe
- Erstellungszeit
- Aktualisierungszeit

In `messages` werden gespeichert:

- Nachricht-ID
- Chat-UUID
- Rolle
- Inhalt
- Zeitstempel

---

### 3.6 `chat_store.py`

`chat_store.py` verwaltet die Chat-Historie.

Unterstützte Operationen:

```text
Chat erzeugen
Chat laden
Nachricht speichern
Nachrichten laden
Hilfestufe setzen
Hilfestufe erhöhen
```

Jeder Chat erhält eine UUID:

```text
8c1182a4-e0d6-4f27-8a84-80b296ddfa76
```

Die Hilfestufe wird maximal bis Level 4 erhöht.

Mögliche Probleme:

- ungültige UUID
- Chat existiert nicht
- Datenbank wurde nicht initialisiert
- Datenbankpfad ist nicht beschreibbar
- Chat-ID gehört zu einer anderen Aufgabe
- parallele Requests verändern dieselbe Hilfestufe
- SQLite ist für einen Prototyp ausreichend, aber nicht für hohe parallele Last ausgelegt
- UUID ist kein Ersatz für Benutzer-Authentifizierung

---

### 3.7 `ollama_client.py`

Der bisherige Client ist für eine native Ollama-API ausgelegt.

Er verwendet:

```text
POST /api/chat
POST /api/generate
```

und Ollama-spezifische Parameter:

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

Die erwartete native Ollama-Antwort enthält:

```json
{
  "message": {
    "role": "assistant",
    "content": "..."
  }
}
```

Das Standardmodell ist `qwen3.6:27b`. Es besitzt 27,8 Milliarden Parameter, ein Kontextfenster von 262.144 Tokens und unterstützt Completion, Tool-Nutzung, Thinking und Vision [1].

---

## 4. Hochschul-LLM-Infrastruktur

### 4.1 Dokumentierte Adresse

Die Moodle-Dokumentation nennt:

```text
https://f2ki-h100-1.f2.htw-berlin.de:11435
```

Als Voraussetzungen werden genannt:

- aktive HTW-VPN-Verbindung
- HTTPS-Verbindung
- keine API-Authentifizierung
- Nutzung der nativen Ollama-Endpunkte

Dokumentierte Endpunkte:

```text
GET    /api/tags
POST   /api/chat
POST   /api/generate
POST   /api/embed
POST   /api/pull
DELETE /api/delete
```

Für den Tutor werden nur benötigt:

```text
GET  /api/tags
POST /api/chat
```

Optional:

```text
POST /api/generate
POST /api/embed
```

Die Endpunkte zum Installieren oder Löschen von Modellen sollten für den Tutor nicht verwendet werden.

---

### 4.2 Tatsächlich sichtbarer Server

Beim Aufruf der Basis-URL im Browser wird derzeit eine Swagger-Dokumentation für:

```text
LiteLLM API 1.99.0
```

angezeigt.

Der sichtbare Server stellt unter anderem folgende OpenAI-kompatiblen Endpunkte bereit:

```text
POST /v1/chat/completions
POST /v1/completions
GET  /v1/models
```

Damit besteht ein Widerspruch zwischen:

```text
Moodle-Dokumentation:
native Ollama-API ohne Token

tatsächliche Basis-URL:
LiteLLM-Proxy mit OpenAI-kompatibler API
```

---

## 5. Durchgeführte Endpunkttests

Ein isoliertes Testskript wurde verwendet, um FastAPI und den eigenen Tutor-Code als Fehlerquelle auszuschließen.

Getestet wurden:

```text
GET  /api/tags
POST /api/chat
POST /v1/chat/completions
```

Ergebnisse:

```text
Native Ollama GET /api/tags
Status: 404
Body: {"detail":"Not Found"}
```

```text
Native Ollama POST /api/chat
Status: 404
Body: {"detail":"Not Found"}
```

```text
LiteLLM POST /v1/chat/completions
Status: 401
Body:
{
  "error": {
    "message": "Authentication Error, No api key passed in.",
    "type": "auth_error",
    "param": "None",
    "code": "401"
  }
}
```

---

## 6. Interpretation der Testergebnisse

Die Ergebnisse zeigen:

1. Die VPN- und HTTPS-Verbindung funktioniert grundsätzlich.
2. Der Server ist erreichbar.
3. Die nativen Ollama-Endpunkte sind auf diesem Host derzeit nicht registriert.
4. Der Host stellt stattdessen einen LiteLLM-Proxy bereit.
5. Der LiteLLM-Endpunkt ist erreichbar.
6. Der LiteLLM-Endpunkt verlangt entgegen der Moodle-Dokumentation einen API-Key.
7. Der Fehler liegt nicht im Prompt-Builder.
8. Der Fehler liegt nicht in der FastAPI-Anwendung.
9. Der Fehler liegt nicht am gewählten Modellnamen.
10. Der Fehler kann nicht allein durch Änderungen am lokalen Client behoben werden.

Ein Netzwerkproblem würde eher zu einem Timeout, DNS-Fehler oder Verbindungsfehler führen. Der Status 404 zeigt dagegen, dass ein Server antwortet, aber den angefragten Pfad nicht anbietet.

---

## 7. Unterschied zwischen den API-Formaten

### 7.1 Native Ollama-API

Endpunkt:

```text
POST /api/chat
```

Request:

```json
{
  "model": "qwen3.6:27b",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein Mathematik-Tutor."
    },
    {
      "role": "user",
      "content": "Gib einen kurzen Hinweis."
    }
  ],
  "stream": false,
  "think": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 400
  }
}
```

Response:

```json
{
  "message": {
    "role": "assistant",
    "content": "..."
  },
  "done": true
}
```

---

### 7.2 LiteLLM/OpenAI-kompatible API

Endpunkt:

```text
POST /v1/chat/completions
```

Request:

```json
{
  "model": "qwen3.6:27b",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein Mathematik-Tutor."
    },
    {
      "role": "user",
      "content": "Gib einen kurzen Hinweis."
    }
  ],
  "stream": false,
  "temperature": 0.2,
  "max_tokens": 400
}
```

Benötigter Header:

```http
Authorization: Bearer API_KEY
```

Response:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

---

## 8. Offizieller HTW-Ollama-Wrapper

Der bereitgestellte Wrapper `examples.py` verwendet weiterhin die nativen Ollama-Endpunkte:

```text
GET  /api/tags
POST /api/chat
POST /api/generate
```

Er setzt keinen Authentifizierungsheader.

Der Wrapper verwendet unter anderem:

```json
{
  "think": false,
  "stream": false,
  "keep_alive": "5m",
  "options": {
    "num_ctx": 2048,
    "temperature": 0.8,
    "seed": 0,
    "num_predict": -1
  }
}
```

Der Wrapper bestätigt damit, dass laut bereitgestelltem Beispiel eine tokenlose native Ollama-API vorgesehen ist.

Wenn der Wrapper derzeit ebenfalls 404 erhält, besteht eine Abweichung zwischen:

```text
bereitgestelltem Wrapper
Moodle-Dokumentation
aktueller Serverkonfiguration
```

---

## 9. Zusätzliche Problematik im HTW-Wrapper

Die Methode:

```python
models = OllamaApi.models()
```

liefert bei einem Fehler `False`.

Anschließend wird ausgeführt:

```python
model_names = [model.get("name") for model in models]
```

Wenn `models` gleich `False` ist, entsteht ein weiterer Fehler, weil ein boolescher Wert nicht iterierbar ist.

Für Diagnosetests sollte daher ein separates Skript verwendet werden, das Statuscode, Header und Body direkt ausgibt.

---

## 10. Empfohlenes Diagnoseskript

```python
import requests


BASE_URL = "https://f2ki-h100-1.f2.htw-berlin.de:11435"


def show_response(name, response):
    print("=" * 70)
    print(name)
    print("URL:", response.url)
    print("Status:", response.status_code)
    print("Server:", response.headers.get("server"))
    print(
        "Content-Type:",
        response.headers.get("content-type")
    )
    print(
        "WWW-Authenticate:",
        response.headers.get("www-authenticate")
    )
    print("Body:")
    print(response.text[:2000])


session = requests.Session()

tags_response = session.get(
    BASE_URL + "/api/tags",
    headers={
        "accept": "application/json"
    },
    timeout=30,
    verify=True
)

show_response(
    "Native Ollama GET /api/tags",
    tags_response
)

chat_response = session.post(
    BASE_URL + "/api/chat",
    headers={
        "Content-Type": "application/json",
        "accept": "application/json"
    },
    json={
        "model": "qwen3.6:27b",
        "messages": [
            {
                "role": "user",
                "content": "Antworte nur mit Test"
            }
        ],
        "think": False,
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_predict": 50
        }
    },
    timeout=180,
    verify=True
)

show_response(
    "Native Ollama POST /api/chat",
    chat_response
)

litellm_response = session.post(
    BASE_URL + "/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "accept": "application/json"
    },
    json={
        "model": "qwen3.6:27b",
        "messages": [
            {
                "role": "user",
                "content": "Antworte nur mit Test"
            }
        ],
        "stream": False,
        "temperature": 0.0,
        "max_tokens": 50
    },
    timeout=180,
    verify=True
)

show_response(
    "LiteLLM POST /v1/chat/completions",
    litellm_response
)
```

---

## 11. Prüfung möglicher Proxy-Probleme

Python `requests` berücksichtigt standardmäßig Proxy-Umgebungsvariablen.

Unter Windows CMD prüfen:

```cmd
set | findstr /I proxy
```

In Python prüfen:

```python
import requests

print(
    requests.utils.get_environ_proxies(
        "https://f2ki-h100-1.f2.htw-berlin.de:11435"
    )
)
```

Zum Testen kann die Verwendung von Umgebungsproxys deaktiviert werden:

```python
session = requests.Session()
session.trust_env = False
```

Wenn die nativen Endpunkte anschließend funktionieren, wurde der Request zuvor über einen ungeeigneten Proxy geleitet.

Da jedoch die LiteLLM-Dokumentation direkt im Browser sichtbar ist, ist eine fehlerhafte Proxy-Konfiguration weniger wahrscheinlich als eine geänderte Serverkonfiguration.

---

## 12. Empfohlene Konfiguration für mehrere API-Modi

Der Tutor-Client sollte langfristig sowohl eine native Ollama-API als auch einen LiteLLM-Proxy unterstützen.

Beispiel für `config.py`:

```python
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
).rstrip("/")

LLM_API_MODE = os.getenv(
    "LLM_API_MODE",
    "ollama"
)

LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    ""
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen3.6:27b"
)

LLM_TIMEOUT = int(
    os.getenv(
        "LLM_TIMEOUT",
        "180"
    )
)
```

Mögliche Modi:

```text
ollama
litellm
```

---

## 13. Authentifizierung für LiteLLM

Falls die Hochschule einen LiteLLM-Key bereitstellt, sollte dieser ausschließlich über eine Umgebungsvariable gesetzt werden.

Windows CMD:

```cmd
set LLM_API_MODE=litellm
set LLM_API_KEY=DEIN_API_KEY
set LLM_BASE_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435
set LLM_MODEL=qwen3.6:27b
```

PowerShell:

```powershell
$env:LLM_API_MODE = "litellm"
$env:LLM_API_KEY = "DEIN_API_KEY"
$env:LLM_BASE_URL = "https://f2ki-h100-1.f2.htw-berlin.de:11435"
$env:LLM_MODEL = "qwen3.6:27b"
```

Der Key darf nicht gespeichert werden in:

```text
Quellcode
Git-Repository
README
Aufgaben-JSON
Browser-URL
Logdateien
```

---

## 14. LiteLLM-Request mit API-Key

```python
import os
import requests


base_url = (
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
)

api_key = os.getenv("LLM_API_KEY")

headers = {
    "Content-Type": "application/json",
    "accept": "application/json",
    "Authorization": f"Bearer {api_key}"
}

payload = {
    "model": "qwen3.6:27b",
    "messages": [
        {
            "role": "system",
            "content": (
                "Du bist ein Mathematik-Tutor."
            )
        },
        {
            "role": "user",
            "content": (
                "Antworte nur mit dem Wort Test"
            )
        }
    ],
    "stream": False,
    "temperature": 0.0,
    "max_tokens": 50
}

response = requests.post(
    base_url + "/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=180,
    verify=True
)

print(response.status_code)
print(response.text)
```

---

## 15. Native Ollama-Nutzung ohne Key

Falls die Hochschule die nativen Routen wieder bereitstellt oder eine andere Ollama-Adresse nennt:

```cmd
set LLM_API_MODE=ollama
set LLM_BASE_URL=https://NEUE-OLLAMA-ADRESSE
set LLM_MODEL=qwen3.6:27b
```

Dann wird verwendet:

```text
POST /api/chat
```

mit:

```json
{
  "model": "qwen3.6:27b",
  "messages": [],
  "think": false,
  "stream": false,
  "keep_alive": "5m",
  "options": {
    "temperature": 0.2,
    "num_predict": 400
  }
}
```

---

## 16. Lokales Ollama als Entwicklungsfallback

Bis der Hochschulzugang geklärt ist, kann der Tutor mit einer lokalen Ollama-Installation entwickelt werden.

Installation:

```text
https://ollama.com/
```

Modell laden:

```cmd
ollama pull qwen3:8b
```

Server starten:

```cmd
ollama serve
```

Umgebungsvariablen:

```cmd
set LLM_API_MODE=ollama
set LLM_BASE_URL=http://127.0.0.1:11434
set LLM_MODEL=qwen3:8b
```

Der lokale Server verwendet:

```text
POST http://127.0.0.1:11434/api/chat
```

Das lokal verfügbare Modell `qwen3:8b` ist deutlich kleiner als das geplante Hochschulmodell. Ergebnisse sollten daher nicht ohne Weiteres als identisch betrachtet werden.

---

## 17. Modellwahl

Für den Tutor ist `qwen3.6:27b` als Ausgangsmodell vorgesehen.

Eigenschaften:

```text
Parameter: 27,8 Milliarden
Quantisierung: Q4_K_M
Kontextfenster: 262.144 Tokens
Fähigkeiten:
- Completion
- Tools
- Thinking
- Vision
```

Diese Eigenschaften sind in der bereitgestellten Modellliste dokumentiert [1].

Weitere mögliche Vergleichsmodelle:

```text
qwen3.8:27b
granite4.1:30b
mistral-medium-3.5:128b
```

Das Modell `qwen3.8:27b` besitzt 27,3 Milliarden Parameter, ein Kontextfenster von 262.144 Tokens und unterstützt Completion, Tools, Thinking und Vision [1].

`granite4.1:30b` besitzt 28,9 Milliarden Parameter, ein Kontextfenster von 131.072 Tokens und unterstützt Completion sowie Tools [1].

`mistral-medium-3.5:128b` besitzt 127,7 Milliarden Parameter, ein Kontextfenster von 262.144 Tokens und unterstützt Completion, Tools, Thinking und Vision [1].

Für den ersten Prototyp sollte nur ein Modell eingesetzt werden:

```text
qwen3.6:27b
```

Ein Modellvergleich kann später mit einem zweiten Modell ergänzt werden.

---

## 18. Umgang mit Thinking-Modellen

`qwen3.6:27b` unterstützt Thinking [1].

Für kurze Tutorhinweise sollte Thinking zunächst deaktiviert werden:

```json
{
  "think": false
}
```

Gründe:

- kürzere Antwortzeit
- geringerer Tokenverbrauch
- besser kontrollierbare Ausgabe
- geringeres Risiko, dass ausschließlich Thinking-Inhalt zurückgegeben wird
- einfachere Reproduzierbarkeit

Beim LiteLLM-Proxy ist `think` kein allgemeiner OpenAI-Parameter. Dort muss geprüft werden, ob der Proxy einen providerspezifischen Parameter unterstützt. Ohne gesicherte Dokumentation sollte dieser Parameter nicht an `/v1/chat/completions` gesendet werden.

---

## 19. Anpassung des LLM-Clients

Der bisherige Dateiname:

```text
ollama_client.py
```

ist nur korrekt, wenn ausschließlich eine native Ollama-API verwendet wird.

Bei Unterstützung mehrerer Backends ist eine neutralere Benennung sinnvoll:

```text
llm_client.py
```

Empfohlene Schnittstelle:

```python
def chat(
    messages,
    model=None,
    temperature=0.2,
    max_tokens=400
):
    ...
```

Die interne Implementierung entscheidet abhängig von:

```text
LLM_API_MODE
```

zwischen:

```text
/api/chat
/v1/chat/completions
```

---

## 20. Fehlerklassen

Sinnvolle Fehlerunterscheidungen sind:

```text
LLMConnectionError
LLMAuthenticationError
LLMEndpointNotFoundError
LLMTimeoutError
LLMInvalidResponseError
LLMModelNotFoundError
```

Beispielhafte Zuordnung:

```text
HTTP 401 oder 403:
Authentifizierungsfehler

HTTP 404:
Endpunkt oder Modell nicht gefunden

HTTP 429:
Rate Limit oder Kapazitätsgrenze

HTTP 500 bis 599:
Server- oder Upstream-Fehler

Timeout:
Modell antwortet nicht rechtzeitig

Leerer Content:
ungültige oder unvollständige Modellantwort
```

Bei `404 {"detail":"Not Found"}` auf `/api/chat` ist der Endpunkt nicht registriert.

Bei `401 Authentication Error, No api key passed in` auf `/v1/chat/completions` fehlt ein LiteLLM-Zugangsschlüssel.

---

## 21. Auswirkungen auf `main.py`

`main.py` wandelt einen Fehler des LLM-Clients derzeit in HTTP 502 um:

```text
Fehler beim Aufruf des Hochschul-LLM
```

Das ist grundsätzlich sinnvoll, weil die lokale FastAPI-Anwendung als Gateway zum externen Hochschuldienst arbeitet.

Es sollte jedoch zwischen Fehlerarten unterschieden werden:

```text
401 vom LLM-Dienst:
lokal als 502 oder 503 mit interner Diagnose behandeln

404 auf API-Endpunkt:
Konfigurationsfehler

Timeout:
504 Gateway Timeout

Rate Limit:
503 Service Unavailable oder 429

sonstiger Upstream-Fehler:
502 Bad Gateway
```

API-Schlüssel und vollständige interne Fehlermeldungen sollten nicht an Studierende ausgegeben werden.

---

## 22. Auswirkungen auf den Prompt-Builder

Der Prompt-Builder ist nicht Ursache des derzeitigen Verbindungsproblems.

Er erzeugt bereits eine standardisierte Nachrichtenliste:

```python
[
    {
        "role": "system",
        "content": "..."
    },
    {
        "role": "user",
        "content": "..."
    }
]
```

Diese Struktur ist sowohl für native Ollama-Chats als auch für OpenAI-kompatible LiteLLM-Chats geeignet.

Unterschiedlich sind nur:

- API-Endpunkt
- Authentifizierungsheader
- Parameterbezeichnungen
- Struktur der Antwort

Der Prompt-Builder kann daher unverändert bleiben.

---

## 23. Auswirkungen auf die Chat-Historie

Die Chat-Historie wird lokal in SQLite gespeichert und ist unabhängig vom verwendeten LLM-Backend.

Der Ablauf lautet:

```text
Chat mit UUID erstellen
    ↓
STACK-Kontext speichern
    ↓
bisherige Nachrichten laden
    ↓
Prompt-Nachrichten erstellen
    ↓
LLM aufrufen
    ↓
Tutorantwort speichern
```

Die SQLite-Datenbank bleibt daher auch bei einem Wechsel von Ollama zu LiteLLM unverändert.

---

## 24. Sicherheitsaspekte

### 24.1 API-Key

Ein später bereitgestellter LiteLLM-Key muss als Geheimnis behandelt werden.

Nicht erlaubt:

```python
LLM_API_KEY = "sk-..."
```

im Quellcode.

Empfohlen:

```text
Umgebungsvariable
lokale .env-Datei
Secret Store
Docker Secret
n8n Credential
```

Die `.env`-Datei muss in `.gitignore` stehen:

```gitignore
.env
```

---

### 24.2 TLS

Da ein gültiges SSL-Zertifikat vorhanden ist, soll verwendet werden:

```python
verify=True
```

Nicht verwenden:

```python
verify=False
```

---

### 24.3 Studierendenantworten

Studierendenantworten sind nicht vertrauenswürdige Eingaben.

Sie dürfen:

- nicht als Systemanweisung interpretiert werden
- nicht ungefiltert als HTML dargestellt werden
- nicht unnötig in externen Logs gespeichert werden
- keine personenbezogenen Daten enthalten

---

### 24.4 Modellverwaltungsendpunkte

Die Moodle-Seite dokumentiert auch:

```text
POST /api/pull
DELETE /api/delete
```

Diese Endpunkte werden vom Tutor nicht benötigt.

Insbesondere `/api/delete` darf nicht verwendet werden.

Die Tutor-Anwendung sollte ausschließlich auf benötigte Inferenzendpunkte beschränkt werden.

---

## 25. Teststrategie

### 25.1 Unit-Tests

Ohne externen LLM-Dienst:

```text
Hint-Policy laden
Hilfestufen prüfen
Kontextfelder ein- und ausschalten
Endlösung vor Level 4 verbergen
Prompt-Nachrichten erzeugen
Chat-Historie speichern
UUID validieren
```

---

### 25.2 Integrationstests

Mit LLM-Dienst:

```text
Verbindung zum API-Endpunkt
Modellname gültig
Chat-Request erfolgreich
Antwortinhalt nicht leer
Timeout-Verhalten
Authentifizierungsfehler
```

Integrationstests sollten markiert werden:

```python
@pytest.mark.integration
```

Ausführung ohne externe Dienste:

```cmd
pytest -m "not integration" -v
```

Ausführung der Integrationstests:

```cmd
pytest -m integration -v
```

---

### 25.3 API-Diagnosetest

Der Endpunkttest sollte getrennt von FastAPI ausgeführt werden.

Damit lassen sich unterscheiden:

```text
Fehler im Tutor-Backend
Fehler im LLM-Client
Fehler im Hochschul-Proxy
Fehler bei Authentifizierung
Fehler bei Modellalias
```

---

### 25.4 Modellliste prüfen

Bei nativer Ollama-API:

```text
GET /api/tags
```

Bei LiteLLM:

```text
GET /v1/models
```

Der LiteLLM-Endpunkt kann ebenfalls einen API-Key verlangen.

Der tatsächlich veröffentlichte Modellalias muss exakt verwendet werden. Ein in einer älteren Modellliste vorhandener Ollama-Name muss nicht zwingend identisch mit dem durch LiteLLM veröffentlichten Alias sein.

---

## 26. Empfohlene Schritte zur Fehlerbehebung

### Schritt 1

VPN-Verbindung prüfen.

```cmd
nslookup f2ki-h100-1.f2.htw-berlin.de
```

---

### Schritt 2

Basis-URL im Browser öffnen.

```text
https://f2ki-h100-1.f2.htw-berlin.de:11435
```

Aktuelles Ergebnis:

```text
LiteLLM API 1.99.0
```

---

### Schritt 3

Native Ollama-Endpunkte testen.

```text
GET  /api/tags
POST /api/chat
```

Aktuelles Ergebnis:

```text
HTTP 404
```

---

### Schritt 4

LiteLLM-Endpunkt testen.

```text
POST /v1/chat/completions
```

Aktuelles Ergebnis:

```text
HTTP 401
No api key passed in
```

---

### Schritt 5

Offiziellen HTW-Wrapper unverändert ausführen.

```cmd
python examples.py
```

Vorher Abhängigkeiten installieren:

```cmd
python -m pip install requests ftfy
```

Wenn auch der offizielle Wrapper 404 erhält, ist die Abweichung gegenüber der Dokumentation reproduziert.

---

### Schritt 6

Proxy-Umgebungsvariablen prüfen.

```cmd
set | findstr /I proxy
```

Optional:

```python
session.trust_env = False
```

---

### Schritt 7

KI-Lab-Support kontaktieren.

Benötigte Klärung:

```text
Wurde die Infrastruktur auf LiteLLM umgestellt
Wie erhält man einen API-Key
Gibt es weiterhin eine tokenlose Ollama-Adresse
Gibt es einen zusätzlichen URL-Präfix
Welche Modellaliase sind für Studierende freigegeben
```

---

### Schritt 8

Bis zur Klärung lokales Ollama verwenden.

```cmd
ollama serve
ollama pull qwen3:8b
```

---

### Schritt 9

Nach Erhalt eines Keys den Client auf LiteLLM umstellen.

```text
POST /v1/chat/completions
Authorization Bearer Header
```

---

### Schritt 10

Nach Bereitstellung einer nativen Adresse den Client auf Ollama konfigurieren.

```text
POST /api/chat
kein Token
```

---

## 27. Nachricht an den KI-Lab-Support

```text
Hallo

ich bin über das HTW-VPN verbunden und teste den in Moodle dokumentierten
Ollama-Dienst unter

https://f2ki-h100-1.f2.htw-berlin.de:11435

Die Basis-URL zeigt derzeit die Swagger-Dokumentation eines LiteLLM-Proxys
in Version 1.99.0

Die dokumentierten tokenlosen Ollama-Endpunkte liefern

GET /api/tags
HTTP 404
{"detail":"Not Found"}

POST /api/chat
HTTP 404
{"detail":"Not Found"}

Der OpenAI-kompatible LiteLLM-Endpunkt

POST /v1/chat/completions

ist erreichbar liefert ohne API-Key jedoch

HTTP 401
Authentication Error No api key passed in

Auch der bereitgestellte HTW-OllamaApi-Wrapper verwendet weiterhin
/api/tags /api/chat und /api/generate und funktioniert daher mit der
aktuellen Serverkonfiguration nicht

Wurde die Infrastruktur von Ollama auf LiteLLM umgestellt

Wie kann ein erforderlicher LiteLLM-Key bezogen werden

Oder gibt es eine andere tokenlose interne Ollama-Adresse beziehungsweise
einen zusätzlichen URL-Präfix

Welcher Modellalias soll für qwen3.6:27b verwendet werden
```

---

## 28. Relevanz für die Thesis

Die aufgetretene Problematik ist auch fachlich relevant.

Sie zeigt die Bedeutung von:

- klar definierten API-Verträgen
- reproduzierbarer Infrastruktur
- Trennung zwischen Tutorlogik und Modellbackend
- konfigurierbaren LLM-Clients
- Fehlerbehandlung
- dokumentierten Modellversionen
- Authentifizierung und Geheimnisverwaltung
- unabhängig testbaren Komponenten

Für die Thesis sollte die Architektur daher nicht fest an einen einzelnen Ollama-Endpunkt gekoppelt werden.

Empfohlen ist eine abstrakte LLM-Schnittstelle:

```text
Tutor-Backend
    ↓
LLM-Client-Abstraktion
    ├── Ollama-Backend
    └── LiteLLM-Backend
```

Dadurch bleibt der Tutor unabhängig davon funktionsfähig, ob das Modell lokal über Ollama oder zentral über LiteLLM bereitgestellt wird.

---

## 29. Aktueller Befund

Der aktuelle Stand ist:

```text
HTW-VPN:
funktioniert

HTTPS-Verbindung:
funktioniert

Basis-URL:
erreichbar

Server:
LiteLLM über Uvicorn

Native Ollama-Endpunkte:
nicht verfügbar

LiteLLM-Endpunkt:
verfügbar

LiteLLM-Authentifizierung:
erforderlich

API-Key:
nicht vorhanden

Tutor-Backend:
nicht Ursache des Fehlers

Prompt-Builder:
nicht Ursache des Fehlers

Nächster notwendiger Schritt:
Klärung mit dem KI-Lab-Support
```

---

## 30. Fazit

Der Tutor-Prototyp ist technisch grundsätzlich korrekt aufgebaut. Das aktuelle Problem entsteht durch eine Inkonsistenz zwischen der dokumentierten HTW-Ollama-Schnittstelle und der tatsächlich bereitgestellten LiteLLM-Infrastruktur.

Die nativen Ollama-Endpunkte liefern HTTP 404. Der vorhandene LiteLLM-Endpunkt verlangt einen API-Key. Ohne eine korrigierte Ollama-Adresse oder einen gültigen LiteLLM-Key kann die Hochschulinstanz derzeit nicht aus dem Tutor angesprochen werden.

Bis zur Klärung sollte:

1. die lokale Entwicklung mit einem lokalen Ollama-Modell fortgesetzt werden
2. der LLM-Client backendunabhängig gestaltet werden
3. der API-Key niemals im Repository gespeichert werden
4. der Hochschulsupport mit den reproduzierbaren Testergebnissen kontaktiert werden
5. der Prompt-Builder und die lokale Chat-Historie unverändert weiterverwendet werden