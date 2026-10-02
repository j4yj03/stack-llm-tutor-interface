# Ordner `code/evaluation/`

Evaluations-Suite für den KI-Tutor: korpusbasierte, reproduzierbare
Tutor-API-Experimente mit getrennter technischer, mathematischer und
didaktischer Auswertung. Konzept und Begründung: `docs/evaluation_protocol.md`
(im Repo-Root `docs/`).

## Grundregeln

1. **Kein Import von `app.main`**: Die Suite nutzt ausschließlich die
    reale HTTP-Schnittstelle (`POST /api/tutor/start`) und berührt weder
    die produktive SQLite-Datenbank noch veraendert sie die Serverkonfiguration.
    Die lokale Notebook-Vorschau importiert nur Schema-/Promptmodule;
    Live-Checks verwenden ausschliesslich die API-`prompt_messages`.
2. **Kein Netz ohne Freigabe**: `validate` und `plan` sind offline.
   Nur `run --execute-live` sendet Requests; vorhandene API-Keys aktivieren
   nichts von selbst.
3. **Frischer Chat je Job**: Ein Job = eine unabhängige Generierung
   (`Fall × Profil × Stufe × Modell × Wiederholung`); keine `chat_id`-Wiederverwendung.
4. **Alle zehn Kontextschalter explizit**: Bedingungen hängen nicht von
   `.env`-Defaults ab.
5. **Korpus trennt Input und Bewertung**: `tutor_context` (potentielle
    Request-Felder) vs. `evaluation_only` (Referenzen, Prüfstatus,
    Provenienz). Referenzschritte/-endloesung werden nur fuer die
    entsprechenden Profile in den Request uebernommen; beim Schritteprofil
    dient die Endloesung zudem als interner Guard-Wert. Bewertungsstatus,
    Aequivalentformen und Provenienz gehen niemals an den Tutor.
6. **Keine stillen Retries, kein stiller Modellwechsel**, unklare
   Transportversuche bleiben unklar; Resume wiederholt nichts automatisch.
7. **Telemetrie ehrlich**: nicht beobachtbare Werte (Token, Upstream-Versuche)
   bleiben `unbekannt`, werden nie geschätzt.

## Bestandteile

| Datei/Ordner | Verantwortung |
|---|---|
| `models.py` | Strenge Datenmodelle (unbekannte Felder → Fehler) |
| `corpus.py` | Fall-/Profil-/Experiment laden, Eignung, Request-Payload |
| `runner.py` | Plan, Manifest, Budget, Versuchsjournal, Resume, Transport |
| `notebook.py` | Auswahl-Snapshots, lokale Prompt-Vorschau, explizit markierte Offline-Demo |
| `checks.py` | Automatische Prüfungen + begrenzte symbolische Formelprüfung |
| `report.py` | Review-Export/-Import, Aggregationen, `derived/report.md` |
| `__main__.py` | CLI (validate/plan/run/check/review-export/review-import/report) |
| `rubric.md` | Bewertungsraster (rubric-1.0) mit Skalenankern |
| `data/` | `context_profiles.json`, Beispielkorpus (`example_cases.jsonl`, synthetische Fixtures), später `cases_research.jsonl` (verifizierte Exporte) |
| `experiments/` | `pilot.json` (Werkzeug-Pilot), `context_core.json` (Hauptvergleich, wartet auf verifizierten Korpus) |
| `notebooks/testbench.ipynb` | **Interaktive Testbench**: Fall-/Profil-/Stufenwahl, Kontext-Checkboxen, Request-/Prompt-Vorschau, Demo/Live/Analyse, Checks, Ratings im Notebook, Tabellen/Diagramme und Export |
| `notebooks/auswertung.ipynb` | Reine Offline-Analyse gespeicherter Läufe; „Run All“ macht keine Netzaufrufe |
| `imports/` | Rohdaten der späteren STACK-/Moodle-Exporte (git-ignoriert) |
| `runs/` | Laufartefakte (git-ignoriert) |

## Kontextprofile

| Profil | extras gegenüber base | Zweck |
|---|---|---|
| `base` | — | Aufgabe + Antwort |
| `diagnosis` | Diagnosecode | strukturierte Diagnose |
| `feedback` | PRT-Feedbacktext | Feedback ohne Code |
| `diagnosis_feedback` | Code + Feedback | inkrementeller Feedback-Effekt |
| `knowledge` | + Lernziele + Regeln | Fachkontext |
| `steps` | + verifizierte Schritte | nur Stufe 3 (Doppelprüfung) |
| `solution` | + Endlösung | nur getrennte Stufe-4-Untersuchung |

`include_score` und `include_chat_history` sind überall `false`.
Wichtig: `include_final_answer=false` bedeutet „Referenzendlösung nicht im
Prompt“ — die **Ausgabe**-Erlaubnis richtet sich nach der Stufe (Stufe 4 ergibt
sie nicht automatisch zu einem Regelverstoß). Der Bericht führt
`complete_solution_present` und `prohibited_disclosure` deshalb getrennt.

## Nutzung

Arbeitsverzeichnis `code/`; eine isolierte Tutor-Instanz mit eigener
`DATABASE_PATH` nutzen (nicht die produktive DB).

### Notebook

Python 3.11 wird fuer die separate Evaluationsumgebung empfohlen:

```bash
python -m pip install -r requirements-evaluation.txt
python -m jupyterlab evaluation/notebooks/testbench.ipynb
```

1. Mit `MODE = 'demo'` alle Zellen ausfuehren: keine Netzwerkaufrufe,
   keine LLMs und keine Datenbank. Die handgeschriebenen Demoausgaben
   zeigen die Checks einschliesslich einer absichtlich offengelegten Loesung.
2. Faelle, Profile und Stufen auswaehlen; fuer `custom` die Kontextfelder
   per Checkbox festlegen. Standard: vier Faelle, drei Profile, Stufen 1/3,
   eine Wiederholung = 24 Jobs. Fuer einen Vergleich `base` beibehalten.
3. Planungszelle ausfuehren und Request/Prompt-Vorschau kontrollieren.
   Korpus, Profile und Experiment werden unter `runs/<RUN_ID>/inputs/`
   eingefroren. Geaenderte Konfiguration erfordert einen neuen `RUN_ID`.
4. Fuer echte Tutorhinweise: `MODE = 'live'`, explizites `MODEL` aus der
   Server-Allowlist, neue `RUN_ID`, `BASE_URL` der isolierten Instanz und
   `EXECUTE_LIVE = True`. Zugangsdaten bleiben auf dem Server.
5. Automatische Checks und Tabellen auswerten; Hinweise fallweise unter
   verschiedenen Profilen vergleichen. Fachliche Ratings im Notebookformular
   speichern oder den neutralen CSV-Bogen extern bewerten und importieren.
6. Berichtszellen nach der Bewertung erneut ausfuehren. CSVs, Diagramme,
   Referenzdaten und Rohprompts liegen nur im git-ignorierten Laufordner.
   `MODE = 'analyze'` mit derselben `RUN_ID` laedt einen bestehenden Lauf
   ohne neue API-Aufrufe.

Der Beispielkorpus enthaelt **12 synthetische Faelle / 4 Aufgabeninstanzen**:

| Funktion | Falltypen | Anzahl |
|---|---|---:|
| `-5*exp(x^2-2*exp(x))` | innere Ableitung fehlt/falsch, Faktor fehlt, korrekte Aequivalentform, Prompt-Injection | 5 |
| `x^2*sin(x)` | Produktregel-Summand fehlt, Potenzableitung falsch, korrekte Antwort | 3 |
| `3*exp(2*x+1)` | innere Ableitung fehlt, konstanter Faktor fehlt | 2 |
| `x^3*exp(x)` | Produktregel-Summand fehlt, Potenzableitung falsch | 2 |

Alle bleiben `draft`, `synthetic_fixture`, `pending`: symbolische lokale
Plausibilitaetstests sind keine STACK-/PRT-Verifizierung. Fuer den Hauptlauf
`CORPUS_FILE` auf belegte, instanzbezogene Faelle setzen und
`ALLOW_UNVERIFIED_CASES = False` verwenden. Fehlende Falldaten fuehren zu
Ausschluessen, nicht zu stillen Kontextaenderungen. Fuer separate
Schritte-/Loesungsuntersuchungen `steps` auf Stufe 3 bzw. `solution` auf
Stufe 4 auswaehlen; niedrige Stufen bleiben trotz gesetzter Checkbox gesperrt.

Ratingboegen sind ohne Modell-/Profilspalten. Fuer eine wirklich blinde
Expertenbewertung nicht vorab die Profilansichten zeigen und
`review_mapping.json` nicht weitergeben. Leere Felder bleiben fehlend;
fachliche Fehler, Stufeneinhaltung und Sprachqualitaet werden getrennt
berichtet. Keine Endloesung erkannt bedeutet `inconclusive`, nie ein
Abwesenheitsbeweis. Demoantworten und ihre Checks/Ratings sind aus
Forschungskennzahlen ausgeschlossen.

Das Notebook findet `code/` auch von seinem Unterverzeichnis aus.
Optional: `TUTOR_EVALUATION_RUNS` fuer einen anderen Artefaktordner und
`TUTOR_BASE_URL` fuer eine andere Tutorinstanz. Nach Kernelneustart kann
`RESUME = True` offene Jobs fortsetzen; das Stundenbudget wird fuer diesen
Lauf aus dem Journal rekonstruiert. Nutzung anderer Laeufe/Clients wird
nicht vom lokalen Runnerbudget erfasst.

### CLI

```bash
# 1) Korpus/Experiment prüfen (offline)
python -m evaluation validate --experiment evaluation/experiments/pilot.json

# 2) Plan + Manifest erzeugen (offline, deterministisch)
python -m evaluation plan --experiment evaluation/experiments/pilot.json \
    --run-dir evaluation/runs/pilot-001 --base-url http://127.0.0.1:8000

# 3) Live ausführen (Rate-Limit: konservativ 35 logische Requests/h)
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live
# Fortsetzen nach Abbruch / Budget-Ende:
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live --resume

# 4) Automatische Prüfungen
python -m evaluation check --run-dir evaluation/runs/pilot-001

# 5) Bewertung: neutraler Bogen -> ausgefüllte CSV importieren
python -m evaluation review-export --run-dir evaluation/runs/pilot-001
python -m evaluation review-import --run-dir evaluation/runs/pilot-001 --file bewertungen.csv

# 6) Auswertung
python -m evaluation report --run-dir evaluation/runs/pilot-001
```

## Kern-Semantik im Überblick

- **Manifest**: eingefrorene Hashes von Experiment, Korpus, Profilen,
  Policy und Quellcode; `--resume` bricht bei Abweichung ab.
- **Journal (`events.jsonl`)**: jeder Versuch wird vor dem Versand
  registriert; ein Abbruch nach Versand erzeugt `transport_ambiguous`
  und wird bei Resume nicht wiederholt.
- **Budget**: Fenster über *abgeschickte* logische Requests (Fehler
  zählen mit), wegen möglicher zwei Upstream-Versuche je Request.
  Bei Resume/Kernelneustart wird das Budget desselben Laufs rekonstruiert.
- **Verifizierung**: `allow_unverified_cases=false` (Hauptlauf) schließt
  Fälle ohne belegte Mathematik aus; der Pilot (Fixtures) ist ein
  Demonstrationsslauf und im Bericht markiert.
- **Fachliche Eignung**: fehlende Diagnose/Feedback/Regeln/Schritte
  schließen das betreffende Profil für den Fall aus; kein Fallback auf
  kleinere Kontexte.
