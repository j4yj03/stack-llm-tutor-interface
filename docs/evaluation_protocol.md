# Evaluationsprotokoll (eval-protocol-1)

Fachliche Test-Suite für den LLM-Tutor: ein Satz an Testaufgaben mit
unterschiedlichen Kontexten wird über die **Tutor-API** (`POST
/api/tutor/start`) abgefragt, ausgewertet und in einem Jupyter-Notebook
analysiert. Grundlage: `docs/expose/expose_4.pdf` (Abschnitt 5.10
technische + fachlich-didaktische Evaluation) und
`code/evaluation/README.md` (Bedienung).

## 1. Forschungsaussage

Untersucht wird ein kontrollierter Korpusvergleich:

> Wie beeinflussen unterschiedliche, fachlich kontrollierte Kontextinformationen
> (Diagnose, Feedback, Lernziele/Regeln, verifizierte Lösungsschritte) die
> Zuverlässigkeit und didaktische Qualität der Tutorhinweise auf einer
> begrenzten Differentialrechnungs-Fallbank?

**Nicht** Gegenstand dieses Protokolls (später getrennt): Live-Diagnosegenauigkeit
von PRT/Maxima, Moodle-Betriebstauglichkeit, Lernwirksamkeit,
direkte Modellbenchmarks.

## 2. Fallbestand (Korpus)

Ein Fall = instanziierte Aufgabe + konkrete Antwort + Bewertung
(`evaluation/data/*.jsonl`, Schema in `evaluation/models.py`).

- `tutor_context`: möglicher Request-Input (Aufgabe, Antwort, Diagnose,
  Feedback, Ziele, Regeln).
- `evaluation_only`: Referenzendlösung, Äquivalentformen, geordnete
  verifizierte Schritte, erwartete Diagnose, Prüfstatus, Provenienz.
  **Fließt nie in einen Request.**
- Referenzen stammen aus STACK-/Moodle-Exporten (Instanz + PRT-Ergebnis +
  Antwort eindeutig verknüpft) oder sind als `synthetic_fixture`
  gekennzeichnet. Keine Forschungsfreigabe ohne Beleg.
- Fehlende Werte = null (nicht `score=0`, nicht erfundene Diagnose).

Freigabe (kann abgeleitet werden, wird nicht behauptet):
`verification.mathematics_status=verified` ist Pflicht für den Hauptlauf
(`allow_unverified_cases=false`). Fixtures laufen nur im Pilot/Tooling.

## 3. Versuchsbedingungen

Kontextprofile (`evaluation/data/context_profiles.json`; alle zehn Schalter
explizit; `include_score` und Historie immer aus):

| Profil | extras | Anmerkung |
|---|---|---|
| base | — | Referenzbedingung |
| diagnosis | Diagnosecode | Kernvergleich |
| feedback | Feedbacktext | Diagnose bewusst aus |
| diagnosis_feedback | Code+Feedback | inkrementeller Effekt |
| knowledge | + Ziele+Regeln | gemeinsamer Fachkontext |
| steps | + verifizierte Schritte | nur Stufe 3 (Doppelprüfung) |
| solution | + Endlösung | nur separate Stufe-4-Untersuchung |

Semantik: `include_final_answer` steuert den **Prompt**, die
Ausgabeerlaubnis folgt der **Stufenpolicy**. Stufe 4 gestattet die
Endlösung — eine vollständige Antwort dort ist kein Regelverstoß. Der
Bericht trennt `complete_solution_present` von `prohibited_disclosure`.
Bestehende Doppelprüfung (`app/prompt_builder.py`) wird nicht abgeschwächt.

## 4. Durchführung

- Ein geplanter Job = ein frischer Chat, direkte Zielstufe, explizites
  Modell, alle Flags; keine `chat_id`-Wiederverwendung; `user_message` leer.
- Seriell, konservativ 35 logische Requests/h (SAIA kann intern einen
  zweiten Versuch je Request auslösen); Fehler und unklare Versuche
  verbrauchen Budget.
- Kein automatischer Retry; `--retry-failed` ist manuell und schließt
  unklare Transportversuche aus.
- Reihenfolge: deterministische Mischung je Lauf (`order_seed`); Pilot- und
  Kernfälle getrennt; keine Promptänderung während eines Hauptlaufs.
- Kernentwurf (nach Freigabe des Korpus):
  `12 Fehlerfälle × 5 Basisprofile × Stufen {1,3} × 2 Wiederholungen` =
  240; plus `steps`-Vergleich (24) und beschriftete Kontrollen. Pilot:
  ~15–20 Requests auf Fixtures (Demonstrationskennzeichnung).

## 5. Auswertung

Ebenen getrennt (kein Kompensations-Mittelwert):

1. **Durchlauf/Betrieb**: outcomes, Fehlbilanzen, Dauer (Median/p95).
2. **Manipulationsprüfung**: Profil/Optionen/Prompt-Konsistenz
   (`checks.jsonl`, Check-Versionen).
3. **Offenlegung**: literal + Äquivalentformen + begrenzte symbolische
   Prüfung (sympy optional); Parse-Fehlschlag = `inconclusive`, niemals
   "nicht enthalten".
4. **Bewertung (rubric-1.0)**: Binärflags (fachlicher Fehler, Widerspruch,
   erfundene Diagnose, Stufeneinhaltung, Lösung, unzulässiger Verrat) und
   Likert 1–5 (Passung, Verständlichkeit, Hilfreichkeit, Aktivierung,
   Präzision). Blind gegenüber Modell/Profil (neutrale `review_id`).
5. **Vergleiche**: gepaarte Differenzen gegen `base` innerhalb desselben
   Falls/Stufe/Wiederholung; Wiederholungen nicht als unabhängige Aufgaben.
6. **Bericht**: `derived/summary.csv`, `paired_comparisons.csv`,
   `report.md`; Notebooks lesen dieselben Artefakte — `testbench.ipynb`
   führt zusätzlich den kompletten Workflow aus (Live-Gate
   `EXECUTE_LIVE=True` entspricht `run --execute-live`).

Berichtspflichten: Fehlversuche bleiben sichtbar; jede Quote mit Abdeckung
(n und N); Bewertungslücken als n ausweisen; keine allgemeine
„Qualitätsnote“, die fachliche Fehler mit Sprachwerten verrechnet.

## 6. Grenzen (aktuell ehrlich dokumentiert)

- Token, Upstream-Versuchszahl, `finish_reason`, Thinking-Fallback:
  von der Tutor-API nicht übermittelt → im Manifest als unbekannt geführt.
- `POST /api/tutor/start` validiert Diagnosen nicht fachlich; die
  Beweislast liegt im Korpus (Provenienz/Belege), nicht in der API.
- Dialog-/Historientypen (Folgefragen) sind erst nach Backend-Fixes
  (Kontextkonsistenz bei Resume, `include_chat_history=false`) geplant.
- Kein LLM-Judge im Standardprozess; ggf. später zusätzlich und getrennt.
