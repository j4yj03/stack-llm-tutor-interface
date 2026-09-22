# Bewertungsraster (rubric-1.0)

Wird vom `review-export` als CSV-Spalten erzeugt und von `review-import`
validiert. Bewertung mit neutraler `review_id`; Modell und Kontextprofil
sind im Bogen absichtlich nicht sichtbar (siehe `review_mapping.json`,
das nicht an Bewerter verteilt wird).

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

## Verfahren

- Ratings gelten pro `review_id` + `rater_id`; Doppelbewertung eines
  Bogens durch dieselbe Person wird beim Import ignoriert.
- Eine nicht bewertete Spalte bleibt leer und zählt als *fehlt* —
  niemals als gut oder bestanden.
- Grundsätzlich: fachliche Sicherheit vor Mittelwerten. Ein fachlich
  falscher Hinweis wird im Bericht einzeln ausgewiesen, nicht durch
  gute Sprachwerte kompensiert.

