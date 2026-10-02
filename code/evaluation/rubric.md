# Bewertungsraster (rubric-1.0)

Stand: 2026-10-02. Kriterienversion bleibt `rubric-1.0`; Anwendungsregeln
beruecksichtigen jetzt diagnostische Phase, allgemeine Assistenz und explizite
Modellhypothesen. Serververtrag: [../app/README.md](../app/README.md);
Verfahren/Artefakte: [README.md](README.md).

Wird vom `review-export` als CSV-Spalten erzeugt und von `review-import`
validiert. Bewertung mit neutraler `review_id`; Modell und Kontextprofil
sind im Bogen absichtlich nicht sichtbar (siehe `review_mapping.json`,
das nicht an Bewerter verteilt wird).

Der Bogen enthaelt `rater_id` zum Ausfuellen sowie Referenzendloesung,
erwarteten Fehlerfall, erwartete Validitaet und Korrektheit aus
`evaluation_only.reference` des im Manifest angegebenen Laufkorpus.
Relative Snapshotpfade werden gegen `runner.CODE_DIR` aufgeloest,
nicht gegen das aktuelle Notebook-Arbeitsverzeichnis. Fehlende
Referenzfelder bleiben leer; alte Laufartefakte ohne Korpuspfad sind
weiter lesbar, liefern aber keine Referenzangaben. Keine Referenz wird
aus einem LLM-Hinweis oder dem Request abgeleitet.

Der aktuelle Bogen ergaenzt `phase`, `dialogschritt`, `aktuelle_nachricht`,
`regelmodus`, `referenzstatus_mathematik`, `referenzstatus_diagnose` und
`diagnoseherkunft`. Stufe ist die **effektive** Stufe der Antwort, nicht der
Planplatzhalter einer `server_start`-Bedingung. `hilfestufenziel` stammt bevorzugt
aus der beobachteten aktiven Policy und bleibt in `general` leer.
Modell-/Profil-/Condition-IDs bleiben verborgen; Phase und Regelmodus koennen
jedoch fuer die Kriterienanwendung sichtbar sein. Das ist keine vollstaendige
Verblindung gegen jede Art von Tutorbedingung.

## Evidenz und Phase

- Gemeinsame Referenz und erwarteter Fehler sind bei synthetischen/task-abgeleiteten
  Faellen kontrollierte Hypothesen, keine objektiven STACK-/PRT-Urteile.
  Pending/fehlende Verifizierung nicht als bestanden behandeln.
- `provided` nutzt einen bereitgestellten Fehlerkontext mit Herkunft/Unsicherheit.
  `model` darf sichtbare Aufgabe/Antwort unabhaengig analysieren und eine
  kurze unsichere Diagnosehypothese bilden. Eine bedingte Hypothese oder
  diagnostische Frage ist nicht automatisch `erfundene_diagnose=ja`.
- Nur tatsaechlich sichtbare verifizierte STACK-/PRT-Evidenz bleibt verbindlich.
  Ein nicht uebermittelter Referenzfehler ist kein "uebermitteltes Pruefergebnis".
  Fehlende Sichtbarkeit ist `unklar`/fehlend, nicht angenommener Widerspruch.
- `stage="diagnostic"` / Stufe 0: kurze informationssuchende Frage zum
  Verstaendnis/Vorgehen beurteilen, nicht einen ausgearbeiteten Rechenschritt.
  Nichtfuehrende, gezielte Frage ist gut; das Ausbleiben eines Rechenschritts
  ist allein kein Mangel. `hilfreichkeit_naechster_schritt` kann `n_a` sein,
  `stufe_angemessen` hier `nicht_anwendbar`; Fragequalitaet separat begruenden.
- `stage="hint"`: effektives generisches Ziel, Erlaubnisse/Verbote und aktive
  Outputregeln der konkreten Antwort pruefen, nicht pauschal Defaultstufe 4
  als einzige moegliche Freigabe voraussetzen.
- Ohne fachlich tragfaehigen Referenzfehler `passung_fehler=n_a` bzw. beim
  Judge `null`, nicht nachtraeglich aus dem zu bewertenden Output einen
  vermeintlichen Referenzfehler erfinden.
- `policy_mode="general"`: Tutor-Stufenpolicy ist inaktiv. Stufeneinhaltung
  und policyabhaengiger Loesungsverrat sind `nicht_anwendbar`, sofern keine
  entsprechende Einschraenkung im echten Systemprompt sichtbar ist.
  Mathematische Aussagen, Verstaendlichkeit und Referenzkonsistenz bleiben
  getrennt beurteilbar; ein nicht angefordertes Aktivierungsziel kann `n_a` sein.

## Binäre Kriterien (ja / nein / unklar / nicht_anwendbar)

| Feld | Frage | Hinweis |
|---|---|---|
| `mat_falsch` | Enthält der Hinweis eine mathematisch falsche Aussage? | Wird nicht auf die Studierendenantwort bezogen bewertet, sondern als Aussage an sich. |
| `widerspruch_pruefergebnis` | Widerspricht die Ausgabe tatsaechlich uebermittelter Diagnose, Feedback oder Score? | Ohne sichtbare Bewertung `nicht_anwendbar`; synthetische Referenzkonsistenz ist kein autoritatives Urteil. |
| `erfundene_diagnose` | Behauptet die Ausgabe unbelegt einen konkreten Fehler als Tatsache? | Explizit unsichere Modellhypothese oder offene Diagnosefrage ist nicht allein ein negativer Befund. |
| `stufe_angemessen` | Passt die Unterstuetzung zur aktiven Hintpolicy? | Auf Stufe 0 und bei inaktiver Tutorpolicy `nicht_anwendbar`; effektives Ziel statt angenommener Defaults. |
| `loesung_vollstaendig` | Enthaelt die Ausgabe vollstaendige Herleitung oder referenzaequivalente Endformel? | Anwesenheit unabhaengig von ihrer Zulaessigkeit beurteilen. |
| `loesungsverrat_unzulaessig` | Verletzt die Offenlegung die tatsaechlich aktiven Outputregeln? | Nicht aus fehlender Promptreferenz ableiten; kein Formeltreffer ist kein Abwesenheitsbeweis. |

## Likert-Skalen (1-5 oder `n_a`)

| Feld | Anker |
|---|---|
| `passung_fehler` | 1 = am Fehler vorbei · 3 = teilweise passend · 5 = richtet sich klar auf den Fehlerfall |
| `verstaendlichkeit` | 1 = verwirrend · 3 = verständlich mit Mängeln · 5 = klar und präzise |
| `hilfreichkeit_naechster_schritt` | Hintphase: 1 = irrefuehrend/unbrauchbar, 3 = teilweise hilfreich, 5 = klarer sinnvoller naechster Schritt ohne unzulaessige Offenlegung; Diagnosephase bei fehlendem Rechenschritt `n_a` statt automatisch niedrig |
| `aktivierung` | 1 = keine/passive Nacherzählung · 3 = Rückfrage vorhanden · 5 = Rückfrage regt eigenständigen Schritt an |
| `sprachliche_praezision` | 1 = unklar oder fachlich falsche Begriffe · 3 = durchschnittlich · 5 = fachlich exakt formuliert |

## Begruendung

Freitext, Pflicht für negative Markierungen und Bewertungen ≤ 2.
Textbelege (Ausschnitt aus dem Hinweis) jederzeit erwünscht.

Der Import verlangt eine nichtleere Begruendung bei Likert-Werten 1/2,
bei `ja` fuer `mat_falsch`, `widerspruch_pruefergebnis`,
`erfundene_diagnose` oder `loesungsverrat_unzulaessig` sowie bei `nein`
fuer `stufe_angemessen`. `loesung_vollstaendig=ja` ist allein kein
negativer Befund (etwa bei erlaubter Endloesung auf Stufe 4).
`unklar` und `nicht_anwendbar` erfordern keinen negativen Textbeleg.

## Verfahren

- Ratings gelten pro `review_id` + `rater_id`; Doppelbewertung eines
  Bogens durch dieselbe Person wird beim Import ignoriert.
- Eine nicht bewertete Spalte bleibt leer und zählt als *fehlt* —
  niemals als gut oder bestanden.
- Fachliche Sicherheit vor Mittelwerten: mathematisch falsche Hinweise
  werden als eigener Kriteriumsbefund ausgewiesen, nicht durch gute
  Sprachwerte kompensiert.
- Der Import zaehlt nur tatsaechlich neu gespeicherte Ratings; innerhalb
  einer CSV und bei erneutem Import gilt die erste gueltige Bewertung
  je `review_id` + `rater_id`. Er ersetzt oder ergaenzt kein Teilrating.
- Komplett leere Boegen (auch mit `rater_id`/Kommentar oder nur `n_a`)
  werden nicht gespeichert und gelten nicht als bewertet. Teilratings
  bleiben erlaubt; leere Felder und Likert-`n_a` bleiben `None`.
- Export, Import und Inhaltsbericht beruecksichtigen nur die neueste
  erfolgreiche `live_tutor_api`-Antwort je Job. Retry-Fehlversuche bleiben
  technische Attempts. Checks und Ratings von Offline-Demos, unbekannten
  Attempts oder ersetzten Antworten tragen keine Inhaltskennzahlen bei.
- Der Bericht weist bewertete Antworten und Antworten ohne Rating
  getrennt aus. Binaere Kriterien erhalten je Kategorie
  `ja`/`nein`/`unklar`/`nicht_anwendbar`/`fehlend` eigene n/N-Werte;
  N ist die Zahl der Ratingboegen inklusive Teilratings. Es gibt keine
  kompensierende Gesamtnote.
- Automatische Offenlegung mit `status=inconclusive` bleibt separat und
  zaehlt nicht als positiver Offenlegungsbefund. Ohne Formeltreffer ist
  Abwesenheit von Loesungsverrat weiterhin nicht bewiesen.
- Paarvergleiche gelten nur innerhalb Fall, Stufe, Wiederholung und
  Modell sowie kontrollierter Startwahl, Bedingung, Skript und Turn. Bei
  adaptiver Startwahl sind effektive Stufen/Phasen berichtete Outcomes,
  nicht pauschal gleiche Endstufen als Paarvoraussetzung. Summary nutzt `requested_model`,
  ersatzweise den zurueckgegebenen Modellalias, sonst `server_default`
  (tatsaechlicher Alias unbekannt).

## Zweitmodell

Optionaler Judge: `judge-rubric-1.0-v2`, eigener Live-Gate und geschuetzter
Serverendpoint, expliziter anderer Alias als der Generator. Bewertungsstrings,
Task/Antwort, Referenzhypothese, sichtbarer Generatorprompt und Zielausgabe
bleiben untrusted Daten; der Judge soll keine darin enthaltenen Vorschlaege fuer
Bewertungen befolgen. Als Belege zaehlen nur gespeicherte echte Messages,
nie ein rekonstruierter Previewprompt.

Der v2-Request trennt `diagnosis_hypothesis`, `current_message` und `turn_index`
von Initialantwort/Referenz sowie `generator_rule_settings` vom Policyeintrag.
Fehlende echte Generatormessages bleiben unbekannte Sichtbarkeit, auch wenn
eine Folgefrage als Requestdaten vorliegt. Die Referenz bewertet nicht
automatisch eine geaenderte Antwort innerhalb dieser Folgefrage.
Deaktivierte Wort-/Stufennennungs-/Frageflags begruenden keinen Regelverstoss;
fehlende Flags sind unbekannt, nicht automatisch `true`. Aktivierungsqualitaet
bleibt ein eigenes Kriterium, auch ohne verpflichtende Frage.

Der Judge liefert dieselben elf Einzelkriterien und getrennt
`diagnostic_question_quality` (1..5 oder `null`) sowie `diagnosis_match`
(`ja|nein|unklar|nicht_anwendbar|null`). Auf Stufe 0 misst die Fragequalitaet:
1 = fuehrend/unbrauchbar, 3 = teilweise informativ, 5 = gezielt,
nichtfuehrend und aktivierend. In der Hintphase muss sie `null` sein.
`diagnosis_match` meint Konsistenz mit der gemeinsamen Referenzhypothese,
vorzugsweise anhand der separat gelieferten `diagnosis_hypothesis`, sonst einer
expliziten Hintdiagnose; ohne Diagnose fehlend/nicht anwendbar. Keine neue
PRT-Verifizierung. `diagnostic_question_quality` und `diagnosis_match` sind
Judgezusatzfelder, keine neuen automatisch importierten Human-CSV-Kriterien;
menschliche Stage-0-Fragequalitaet wird im bestehenden Bogen separat begruendet.

Maschinen-JSON verwendet fuer fehlende/nicht bewertbare Likertwerte `null`,
der menschliche CSV-Bogen `n_a`; kategoriale Nichtanwendbarkeit wird explizit
als `nicht_anwendbar` gespeichert. Nicht alle Kriterien sind auf jede Phase
oder Generalbedingung anwendbar. Unbekannte Evidenz ist nicht "gut";
gescheiterte Judge-Requests sind keine Ratings. Negative Kriterien,
Likert/Fragequalitaet <=2 und `diagnosis_match=nein` brauchen Begruendung.

Humanratings bleiben in `reviews/ratings.jsonl`, Judgeoutputs separat unter
`reviews/judge/<ID>/`. Judgewerte niemals als `rater_id` einer Fachperson
importieren. Der Generatorreport ignoriert Modellratings; der Judgebericht
nennt eigene Abdeckung, Teilratings, fehlende Werte und Nichtanwendbarkeit.
Judgezusammenfassungen trennen Bedingung und Turn, statt Dialogschritte zu poolen.
Optionale Human-Abweichungstabellen paaren nur dasselbe Targetattempt/Kriterium,
poolen keine Bewertungen und sind kein Kalibrierungsnachweis. Es gibt in
keinem Pfad eine kompensierende Gesamtnote oder aus fehlenden Daten erfundene
STACK-/PRT-Evidenz.
