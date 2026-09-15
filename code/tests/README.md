# Ordner `code/tests/`

Pytest-Suite des Prototyps. Konfiguration in `pytest.ini`
(Marker `integration: Tests mit externen Diensten`).

## Ausführen

```bash
pytest -m "not integration" -v   # Unit-Tests, keine Netzwerkzugriffe
pytest -m integration -v         # echte LLM-Aufrufe (API-Key in .env nötig)
pytest                           # alles; Integrationstests werden ohne Key automatisch übersprungen
```

Kompatibilitäts-Abhängigkeiten für Tests werden wie die Anwendung aus
`requirements.txt` installiert; der Testclient benötigt zusätzlich `httpx2`.

## Dateien

| Datei | Inhalt |
|---|---|
| `conftest.py` | gemeinsame Fixtures: `hint_policy`, `prompt_builder`, `stack_context`, isolierter `chat_store` (tmp-SQLite) |
| `test_api.py` | FastAPI-Endpunkte mit **gemocktem LLM**: `/health`, `/api/tutor/start`, HTTP 429- und 502-Mapping |
| `test_hint_policy.py` | alle generischen Stufen laden; unvollständige/ungültige Stufen werfen `HintPolicyError` |
| `test_prompt_builder.py` | Nachrichtenstruktur: System-/User-Rollen, Stufenregeln, Prompt-Injection-Isolation der Studierendenantwort |
| `test_solution_disclosure.py` | Lösungspreisgabe: `solution_steps`/`final_answer` nur bei Doppel-Erlaubnis (Option **und** Stufe) im Kontext |
| `test_chat_store.py` | UUID-Erzeugung/-Validierung, Nachrichtenreihenfolge, Stufengrenze bei 4 |
| `test_llm_factory.py` | Backend-Wahl (`saia`/`litellm`-Alias/`ollama`), unbekannter Modus, Kompatibilitäts-Wrapper delegiert |
| `test_llm_saia.py` | SAIA-Client mit gemocktem `app.llm._http.SESSION`: Happy Path, 401→Auth, 429→RateLimit (Retry-After), 500→Connection, leere/ungültige Antworten, Thinking-Flag |
| `test_llm_ollama.py` | nativer Ollama-Fallback: Happy Path, leere/fehlende Antworten |
| `test_llm_integration.py` | **integration**: echter SAIA-Call liefert nichtleeren Hinweis |
| `test_tutor_regression.py` | **integration**: Stufe-1-Hinweis enthüllt die Endlösung nicht (String-Gegenprüfung; symbolische Prüfung via STACK/Maxima ist geplant) |
| `scripts/` | eigenständige Diagnose-Skripte, kein Bestandteil der Testausführung (siehe `scripts/README.md`) |

## Konventionen

- Unit-Tests mocken externe Dienste grundsätzlich (`monkeypatch` auf `app.llm._http.SESSION` bzw. `main_module.create_llm_client`) – kein Netzwerk.
- Lösungsdisclosure-Tests prüfen den Prompt-**Kontext**; Output-Checks beurteilen generierte Antworten.
- Neue Kontextoptionen: Unit-Tests für an-/abgeschalteten Zustand inkl. Lösungensschutz ergänzen (siehe AGENTS.md).
