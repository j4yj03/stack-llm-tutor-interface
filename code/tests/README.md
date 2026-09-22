# Ordner `code/tests/`

Pytest-Suite des Prototyps. Konfiguration in `pytest.ini`
(Marker `integration: Tests mit externen Diensten`).

## Ausführen

```bash
pytest -m "not integration" -v   # Unit-Tests, keine Netzwerkzugriffe
pytest -m integration -v         # echte LLM-Aufrufe (API-Key in .env nötig)
pytest                           # alles; Integrationstests werden ohne Key automatisch übersprungen
node --test tests/test_moodle_snippets.js  # STACK-JS mit gemockter Bridge, optional Node >=18
```

Test-Abhängigkeiten werden wie die Anwendung aus `requirements.txt` installiert.
Der Testclient nutzt hier `httpx` (Starlette meldet dessen spätere Ablösung durch
`httpx2` als Deprecation). Vorhandene AnyIO-/Pydantic-Deprecations sind ebenfalls
noch kein Testfehler. Integrationstests nicht zur Prüfung dieses UI-Umbaus starten:
sie verbrauchen echte LLM-Aufrufe.

## Dateien

| Datei | Inhalt |
|---|---|
| `conftest.py` | gemeinsame Fixtures: `hint_policy`, `prompt_builder`, `stack_context`, isolierter `chat_store` (tmp-SQLite) |
| `test_api.py` | FastAPI-Endpunkte mit **gemocktem LLM** und isolierter SQLite-DB: HTML-Chat/Folgehints, Retry-Endpunkt (Wiederholung ohne Frage-Dublette, Versuchsstufe, Stufenregeln), exakter Debug-Prompt, Moodle-Varianten (`question_text`/`funktion`), Modell-/Längenvalidierung, Escaping, UUID-Fehler, API-Verlauf, HTTP 429/502, keine Rückstufung und Browser-LF/CRLF |
| `test_task_loader.py` | Textbaustein-Validierung (`{funktion}`-Platzhalter, Länge) und Generik-Prüfung der echten Aufgaben: keine festen Beispielwerte in Frage text, Template, Lernzielen, Diagnosen und `given_data` |
| `test_hint_policy.py` | alle generischen Stufen laden; unvollständige/ungültige Stufen werfen `HintPolicyError` |
| `test_prompt_builder.py` | Nachrichtenstruktur: System-/User-Rollen, Stufenregeln, Prompt-Injection-Isolation der Studierendenantwort |
| `test_solution_disclosure.py` | Lösungspreisgabe: `solution_steps`/`final_answer` nur bei Doppel-Erlaubnis (Option **und** Stufe) im Kontext |
| `test_moodle_snippets.js` | Node-eigene Tests mit VM-/DOM-/STACK-JS-Testdoubles: Input-Sync, Encoding, Zufallsformeln, sichere CASText-Einbettung, Diagnosebindung und asynchrone Fälle |
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
- Import der App validiert die lokalen Aufgaben gegen ihr JSON-Schema; Lösungsschutztests verwenden zusätzlich beide echten Aufgaben statt nur der vereinfachten Fixture.
- Die Node-Tests führen weder Maxima noch Moodle aus. Manueller STACK-Testplan: `../moodle/README.md`.
