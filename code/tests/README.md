# Ordner `code/tests/`

Stand: 2026-10-02. Pytest-Suite des Prototyps. Konfiguration in `pytest.ini`
(Marker `integration: Tests mit externen Diensten`).
Serververtraege: [../app/README.md](../app/README.md); Parameter:
[../config/README.md](../config/README.md); Evaluation:
[../evaluation/README.md](../evaluation/README.md).

## Ausführen

```bash
python -m pytest -m "not integration" -v
node --test tests/test_moodle_snippets.js
```

Aus `code/`; Node alternativ ab Repo-Root mit
`node --test code/tests/test_moodle_snippets.js`. Integrationstests nur nach
expliziter Freigabe mit `python -m pytest -m integration -v` ausfuehren.
Ungefiltertes `pytest` ist kein sicherer Offlineaufruf: konfigurierte Keys
koennen echte LLM-Aufrufe aktivieren. Vorhandene Tokens sind ebenfalls keine
Freigabe fuer Livebatches/Judge.

Test-Abhaengigkeiten werden wie die Anwendung aus `requirements.txt` installiert;
fuer Notebook-/vollstaendige Evaluationstests zusaetzlich
`requirements-evaluation.txt`. Python 3.11 ist die Referenzumgebung, die
Requirements-Dateien sind keine vollstaendigen Environment-Locks.
Der Testclient nutzt hier `httpx` (Starlette meldet dessen spätere Ablösung durch
`httpx2` als Deprecation). Vorhandene AnyIO-/Pydantic-Deprecations sind ebenfalls
noch kein Testfehler. Integrationstests nicht fuer eine reine Offlinepruefung starten:
sie verbrauchen echte LLM-Aufrufe.

## Dateien

| Datei | Inhalt |
|---|---|
| `conftest.py` | gemeinsame Fixtures: `hint_policy`, `prompt_builder`, `stack_context`, isolierter `chat_store` (tmp-SQLite) |
| `test_api.py` | FastAPI-Endpunkte mit **gemocktem LLM** und isolierter SQLite-DB: HTML-Chat/Folgehints, Retry-Endpunkt (Wiederholung ohne Frage-Dublette, Versuchsstufe, Stufenregeln), exakter Debug-Prompt, Moodle-Varianten (`question_text`/`funktion`), Modell-/Längenvalidierung, Escaping, UUID-Fehler, API-Verlauf, HTTP 429/502, keine Rückstufung, Browser-LF/CRLF sowie KaTeX-Einbindung (SRI/no-referrer) und CAS-zu-LaTeX-Anzeige mit rohem Fallback |
| `test_tutor_rules.py` | Gemockte echte API-Roundtrips: Stage 0, Requestflags bei Startwahl, effektiver Historiencap, Adaption/Simulationsauth, aktive Configidentitaet, begrenzte strukturierte Texte, additive DB-Migration und Task-/Skriptpayloads |
| `test_task_loader.py` | Textbaustein-Validierung (`{funktion}`-Platzhalter, Länge) und Generik-Prüfung der echten Aufgaben: keine festen Beispielwerte in Frage text, Template, Lernzielen, Diagnosen und `given_data` |
| `test_config.py` | Fail-fast-Umgebungsparsing, Stufen-/Token-/Temperaturgrenzen, Modi, Stage-0-Flags, Pfadaufloesung und Evaluationtokenpflicht |
| `test_runtime_config.py` | Effektive Kontextflags, Stage-0-Obergrenze ohne Requestmutation, Diagnosefilter, geheimnisfreier Snapshot und kanonische Hashidentitaet |
| `test_hint_policy.py` | Alle aktiven Stufen inklusive 0; Pflichtfelder/Typen, explizite Policydatei, JSON-/per-Level-Praezedenz und keine unsichere Templatierung |
| `test_prompt_builder.py` | Rollen/Isolation, aktuelle Nachricht ohne Historie, Diagnoseherkunft, Modellanalyse, Tutor/General und strukturierte Antwortvorgabe |
| `test_solution_disclosure.py` | Lösungspreisgabe: `solution_steps`/`final_answer` nur bei Doppel-Erlaubnis (Option **und** Stufe) im Kontext |
| `test_math_notation.py` | Whitelist-Konvertierung STACK-/Maxima-Syntax nach LaTeX (nur Anzeige): typische Ausdrücke, Gleichungen, Fakultät, Fallback None für Prosa/unsichere Syntax, kein eval |
| `test_moodle_snippets.js` | Node-eigene Tests mit VM-/DOM-/STACK-JS-Testdoubles: Input-Sync, Encoding, Zufallsformeln, sichere CASText-Einbettung, Diagnosebindung und asynchrone Fälle |
| `test_chat_store.py` | UUIDs, Reihenfolge und Persistenz; Stufengrenzen aus `MIN_HINT_LEVEL`/`MAX_HINT_LEVEL`, Baseline-/Zustandsvertrag bei Erweiterungen beachten |
| `test_llm_factory.py` | Backend-Wahl (`saia`/`litellm`-Alias/`ollama`), unbekannter Modus, Kompatibilitäts-Wrapper delegiert |
| `test_llm_saia.py` | SAIA-Client mit gemocktem `app.llm._http.SESSION`: Happy Path, 401→Auth, 429→RateLimit (Retry-After), 500→Connection, leere/ungültige Antworten, Thinking-Flag |
| `test_llm_ollama.py` | Nativer Ollama-Fallback: Antwortfehler, konfiguriertes `think` und `format="json"` bei JSONmodus |
| `test_llm_integration.py` | **integration**: echter SAIA-Call liefert nichtleeren Hinweis |
| `test_tutor_regression.py` | **integration**: Stufe-1-Hinweis enthüllt die Endlösung nicht (String-Gegenprüfung; symbolische Prüfung via STACK/Maxima ist geplant) |
| `test_task_cases.py` | Authored Taskbeispiele, eindeutige IDs/Fehlerreferenzen, instanzpassende Ableitung, pending/synthetische Provenienz und keine erfundenen Scores/Seeds |
| `test_evaluation_corpus.py` | Strikte Faelle/Profile, Datenverfuegbarkeit und Referenz-/Payloadtrennung |
| `test_evaluation_runner.py`, `test_evaluation_conditions.py` | Offlineplaene, Bedingungs-/Skripthashes, Live-Gate, Configpreflight/-drift, Turnabhaengigkeiten, gewichtetes Budget, Ambiguitaet und Resume |
| `test_evaluation_checks.py` | Tatsaechliche Prompts/effektive Flags/aktive Policy, deaktivierte Regeln, Doppelguard und begrenzte sichere Symbolik |
| `test_evaluation_report.py` | Humanratingimport, neutrale Referenzen, Teilratings, Demofilter und bedingungs-/phasen-/turnbewusste Paare |
| `test_evaluation_judge.py` | Eigener Live-Gate, expliziter verschiedener Alias, authentifizierter Config-/Judgevertrag, Targethashes, getrennte Journale und keine Humanratingkontamination |
| `test_evaluation_notebook.py` | Outputfreie Notebooks, Offlineausfuehrung mit temporaeren Artefakten und gemockte Generierungs-/Rating-/Reportpfade |
| `scripts/` | eigenständige Diagnose-Skripte, kein Bestandteil der Testausführung (siehe `scripts/README.md`) |

## Konventionen

- Unit-Tests mocken externe Dienste grundsätzlich (`monkeypatch` auf `app.llm._http.SESSION` bzw. `main_module.create_llm_client`) – kein Netzwerk.
- Lösungsdisclosure-Tests prüfen den Prompt-**Kontext**; Output-Checks beurteilen generierte Antworten.
- Neue Kontextoptionen: Unit-Tests für an-/abgeschalteten Zustand inkl. Lösungensschutz ergänzen (siehe AGENTS.md).
- Import der App validiert die lokalen Aufgaben gegen ihr JSON-Schema; Lösungsschutztests verwenden zusätzlich beide echten Aufgaben statt nur der vereinfachten Fixture.
- Die Node-Tests führen weder Maxima noch Moodle aus. Manueller STACK-Testplan: `../moodle/README.md`.

## Pruefvertraege

- Policyfixtures brauchen jetzt explizit Level 0; kein stilles Upgrade einer
  alten Custompolicy. Defaultstufen 1..4 bleiben unveraendert, invalid ist -1,
  nicht mehr 0. Eigene Maxima verlangen vollstaendige aktive Policies.
- Starttests unterscheiden explizites Level, fehlendes/null-Level mit fester
  Baseline und individuelle Auswahl mit zusaetzlicher gemockter LLM-Operation.
  Fehlende Auswahl/Hintgenerierung darf keinen erfundenen Erfolg liefern.
- Folgeadaption nur bei naechster Interaktion, Schwelle plus Selbstbericht,
  Ceiling/keine Rueckstufung, Erfolgscommit und persistierte Baseline pruefen.
  Skriptintervalle als Simulation markieren; keine echten Waits oder Lernzeit
  voraussetzen. Zeit allein erhoeht keine Stufe. Monotone Prozessuhr, unbekannte
  Intervalle nach Neustart/Workerwechsel und nichtsticky Simulation pruefen.
- `model` erlaubt unabhaengige unsichere Fehleranalyse; `provided|none`
  behalten das Neubewertungsverbot. Synthetische Herkunft nie als PRT pruefen.
  Tatsaechlich bereitgestellte verifizierte Evidenz bleibt verbindlich.
- Generalprompt darf keine inaktive Tutor-Stufen-/Wort-/Fragepolicy erzwingen;
  untrusted Isolation und Referenz-Doppelfreigaben muessen bestehen bleiben.
- Config- und Judgeauth pruefen: deaktiviert 404, falscher Token 401,
  aktiviert ohne Token Startfehler. Keine Tokenwerte in Artefakten. Modellalias
  verschieden pruefen, ohne daraus statistische Unabhaengigkeit abzuleiten.
- Journal vor Dispatch, Kosten 4/2, gemeinsames serielles Runbudget,
  Driftblockade und kein Replay fehlgeschlagener Folge-POSTs testen.
  Produktive DB, reale vorhandene Runs und eingecheckter Korpus bleiben tabu.
- Human-/Judgeratings strikt getrennt; fehlend/unklar/nicht_anwendbar,
  Begruendung negativer Befunde und kein kompensierender Gesamtscore. Judge v2
  beurteilt separate Hypothese, aktuelle Nachricht, Regelsettings und Turn;
  fehlende echte Generatormessages bleiben unbekannt.

Fokussierte Offlinepruefung des Evaluationspfads aus `code/`:

```bash
python -m pytest tests/test_task_cases.py tests/test_evaluation_corpus.py \
    tests/test_evaluation_conditions.py tests/test_evaluation_runner.py \
    tests/test_evaluation_checks.py tests/test_evaluation_report.py \
    tests/test_evaluation_judge.py tests/test_evaluation_notebook.py \
    -m "not integration" -v
```

Optionale Abhaengigkeiten koennen explizite Skips verursachen; Skips sind kein
Funktionsnachweis. Diese Dokumentation nennt bewusst keine globale Passzahl
oder Aussage ueber noch in Arbeit befindliche Notebook-/Integrationstests.
Externes STACK-Grading, Deploymentauthentifizierung und vollstaendige
Output-Loesungsdetektion bleiben getrennte Abnahmeaufgaben.
