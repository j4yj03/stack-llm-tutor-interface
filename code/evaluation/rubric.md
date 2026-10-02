# Bewertungsraster (rubric-1.0)

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

## Binäre Kriterien (ja / nein / unklar / nicht_anwendbar)

| Feld | Frage | Hinweis |
|---|---|---|
| `mat_falsch` | Enthält der Hinweis eine mathematisch falsche Aussage? | Wird nicht auf die Studierendenantwort bezogen bewertet, sondern als Aussage an sich. |
| `widerspruch_pruefergebnis` | Widerspricht der Hinweis dem übermittelten Prüfergebnis/diagnose? | `nicht_anwendbar`, wenn keine Diagnose bereitgestellt wurde. |
| `erfundene_diagnose` | Unterstellt der Hinweis ein konkretes Fehlermuster, das nicht belegt war? | Ohne Diagnose-Kontext: allgemeine Hinweise sollen nicht spekulieren. |
| `stufe_angemessen` | Passt die Unterstützung zur angegebenen Hilfestufe? | Zielpolicy steht im Bogen (Stufenziel). |
| `loesung_vollstaendig` | Enthält der Hinweis die vollständige Lösung oder eine zur Referenz äquivalente Endformel? | Auf Stufe 4 grundsätzlich erlaubt: Bedeutung nur zusammen mit dem nächsten Feld. |
| `loesungsverrat_unzulaessig` | Verstößt die Offenlegung gegen die Stufenregel? | Stufe≠4 und vollständige Endlösung ⇒ in der Regel ja. Literal fehlende Formel ist kein Beweis für Abwesenheit. |

## Likert-Skalen (1-5 oder `n_a`)

| Feld | Anker |
|---|---|
| `passung_fehler` | 1 = am Fehler vorbei · 3 = teilweise passend · 5 = richtet sich klar auf den Fehlerfall |
| `verstaendlichkeit` | 1 = verwirrend · 3 = verständlich mit Mängeln · 5 = klar und präzise |
| `hilfreichkeit_naechster_schritt` | 1 = irreführend/unbrauchbar · 3 = teilweise hilfreich, vage · 5 = klarer, rechnerisch sinnvoller nächster Schritt ohne unzulässige Offenlegung |
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
  Modell. Summary und Paarvergleich nutzen `requested_model`,
  ersatzweise den zurueckgegebenen Modellalias, sonst `server_default`
  (tatsaechlicher Alias unbekannt).
