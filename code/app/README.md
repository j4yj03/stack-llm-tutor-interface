# Paket `code/app/`

FastAPI-Anwendung des KI-Tutors. Entrypoint: `app.main:app`.

## Datenfluss

```text
Moodle/STACK → GET /start → main.py
    → task_loader (Aufgabe laden, validieren)
    → ChatStore (Session per UUID anlegen/fortsetzen)
    → HintPolicy (generische Stufen-Regeln)
    → PromptBuilder (System- + Kontext-Nachrichten)
    → app.llm (Backend-Fabrik → SAIA/Ollama)
    → ChatStore (Antwort speichern)
    → tutor_page.html / JSON-Antwort
```

## Dateien

| Datei | Verantwortung |
|---|---|
| `main.py` | FastAPI-Entrypoint; alle REST-Endpunkte; Validierung von `qid`, `diagnosis`, `ans1`, Modell-Allowlist; Fehlermapping LLM→HTTP (429/502) |
| `config.py` | Zentrale Konfiguration: Pfade, `LLM_*`-Umgebungsvariablen, `ALLOWED_MODELS`, Limits (`MAX_STUDENT_ANSWER_LENGTH`, `MAX_HISTORY_MESSAGES`, `MAX_HINT_LEVEL`) |
| `schemas.py` | Pydantic-Modelle: `ContextOptions`, `StackContext`, `TutorRequest`, `NextHintRequest`, `UserChatRequest`, `ChatMessage`, `TutorResponse`, `ChatHistoryResponse` |
| `database.py` | `initialize_database()`, `get_connection()`; SQLite mit Foreign Keys (`ON DELETE CASCADE`) |
| `chat_store.py` | CRUD für Chats/Nachrichten; UUID-Validierung; `next_hint_level` stoppt bei `MAX_HINT_LEVEL` |
| `hint_policy.py` | Lädt `config/hint_levels.json`; prüft Stufen 1..4 vollständig; `HintPolicyError` bei Fehlern |
| `prompt_builder.py` | System-Nachricht (Tutorrolle, Stufenregeln, Prompt-Injection-Schutz) + Kontext-Abschnitte je nach `ContextOptions`; Doppelprüfung bei `solution_steps`/`final_answer` (Option **und** Stufe) |
| `task_loader.py` | Lädt `tasks/*.json`, validiert gegen JSON-Schema (Draft 2020-12), erzwingt eindeutige `question_id`s; Fail-fast bei ungültigen Dateien |
| `ollama_client.py` | Kompatibilitäts-Wrapper (`call_ollama_chat` u. a. delegieren an `app.llm.create_llm_client`) |

## Endpunkte (main.py)

| Route | Methode | Zweck |
|---|---|---|
| `/health` | GET | Health-Check inkl. geladener Aufgaben und Default-Modell |
| `/tasks` | GET | Liste der verfügbaren Aufgaben |
| `/start` | GET | Moodle/STACK-Adapter (HTML-Seite) |
| `/api/tutor/start` | POST | Tutor-Session starten |
| `/api/tutor/{chat_id}/next-hint` | POST | Nächste Hilfestufe (inkrementiert, max. 4) |
| `/api/tutor/{chat_id}/message` | POST | Folgefrage stellen (Stufe bleibt gleich) |
| `/api/tutor/{chat_id}/history` | GET | Chatverlauf abrufen |

## Sicherheitsregeln

- Studierendenantworten sind **nicht vertrauenswürdig**: Längenlimit, Isolation in `<student_answer>`-Tags, keine Interpolation in System-Nachrichten.
- Nur Modelle aus `ALLOWED_MODELS` sind über Request-Parameter wählbar.
- Das LLM darf STACK-Score, PRT-Diagnose und Bewertungsinstanz nicht überschreiben.
- API-Keys nur über `.env`/Umgebung; niemals loggen oder committen.
