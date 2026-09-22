# Ordner `code/evaluation/`

Evaluations-Suite für den KI-Tutor: korpusbasierte, reproduzierbare
Tutor-API-Experimente mit getrennter technischer, mathematischer und
didaktischer Auswertung. Konzept und Begründung: `docs/evaluation_protocol.md`
(im Repo-Root `docs/`).

## Grundregeln

1. **Kein Import von `app.main`**: Die Suite nutzt ausschließlich die
   reale HTTP-Schnittstelle (`POST /api/tutor/start`) und berührt weder
   die produktive SQLite-Datenbank noch die Serverkonfiguration.
2. **Kein Netz ohne Freigabe**: `validate` und `plan` sind offline.
   Nur `run --execute-live` sendet Requests; vorhandene API-Keys aktivieren
   nichts von selbst.
3. **Frischer Chat je Job**: Ein Job = eine unabhängige Generierung
   (`Fall × Profil × Stufe × Modell × Wiederholung`); keine `chat_id`-Wiederverwendung.
4. **Alle zehn Kontextschalter explizit**: Bedingungen hängen nicht von
   `.env`-Defaults ab.
5. **Korpus trennt Input und Bewertung**: `tutor_context` (potentielle
   Request-Felder) vs. `evaluation_only` (Referenzen, Prüfstatus,
   Provenienz — niemals im Request).
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
| `checks.py` | Automatische Prüfungen + begrenzte symbolische Formelprüfung |
| `report.py` | Review-Export/-Import, Aggregationen, `derived/report.md` |
| `__main__.py` | CLI (validate/plan/run/check/review-export/review-import/report) |
| `rubric.md` | Bewertungsraster (rubric-1.0) mit Skalenankern |
| `data/` | `context_profiles.json`, Beispielkorpus (`example_cases.jsonl`, synthetische Fixtures), später `cases_research.jsonl` (verifizierte Exporte) |
| `experiments/` | `pilot.json` (Werkzeug-Pilot), `context_core.json` (Hauptvergleich, wartet auf verifizierten Korpus) |
| `notebooks/testbench.ipynb` | **Komplette Test-Bench**: führt alle Phasen (validate → plan → run → check → review → report → Analyse) über dieselben Funktionen wie das CLI aus; Live-Ausführung nur mit explizitem Gate `EXECUTE_LIVE = True` |
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
- **Verifizierung**: `allow_unverified_cases=false` (Hauptlauf) schließt
  Fälle ohne belegte Mathematik aus; der Pilot (Fixtures) ist ein
  Demonstrationsslauf und im Bericht markiert.
- **Fachliche Eignung**: fehlende Diagnose/Feedback/Regeln/Schritte
  schließen das betreffende Profil für den Fall aus; kein Fallback auf
  kleinere Kontexte.
