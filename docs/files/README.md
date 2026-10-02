# Ordner `docs/files/`

**Status: Quellenindex historischer Einzelnotizen, 2026-10-02.** Exportierte
Notion-/Word-Arbeitsmaterialien und Snippets dienen als Entwicklungsarchiv,
nicht als aktive Code-, Evidenz- oder Betriebsspezifikation. Aktuelles Design:
[eval-protocol-2](../evaluation_protocol.md).

## Bestand und Belegwert

| Datei | Inhalt und heutige Einordnung |
|---|---|
| `Aufgabe.txt`, `Aufgabe_Fehlerbeschreibung.csv` | Beispielaufgabe und authorierte Fehlerszenarien, keine dokumentierten PRT-Pruefergebnisse |
| `json_schema.txt`, `aufgaben_json.txt` | Fruehe Formatentwuerfe; aktuelles Schema unter `code/schemas/`, aktueller [Nachtrag](../json_schema_info.md) |
| `Fast API app.txt`, `Dateistruktur Prototyp.txt` | Fruehe App-/Strukturideen, nicht die heutigen Routen oder Pfade |
| `Bsp für erzeugtes Prompt.txt` | Promptbeispiel; ohne Run-/Requestbezug kein beobachteter Serverprompt und kein Modellresultat |
| `moodlelink.txt`, `FeedbackLink.txt`, `URL encoding.txt`, `Question variable.txt` | Historische Integrationsideen; aktuelle Feldbausteine in [code/moodle](../../code/moodle/README.md) |
| `TutorDaten.txt` | Frueher Sessionentwurf, nicht das heutige SQLite-Migrationsschema |
| `requirements.txt` | Abhaengigkeitsnotiz, nicht der aktuelle gepinnte Server-/Notebookstand |

## Aktuelle Trennung

Die optionale Task-Struktur `evaluation_examples` authoriert jetzt 15 konkrete
synthetische Antworten fuer explizite, referenzpassende Funktionen. Der
Taskexport bleibt `draft`/`synthetic_fixture` mit offener Pruefung (`pending`).
Keinen Fehlerkey, eine Formel oder einen Beispielprompt aus diesem Archiv
als bereits erwiesenes STACK-/PRT-Ergebnis importieren.

Reale Generatorausgaben liegen mit echten Prompts, Policy-/Konfigurations-
Snapshots, Hashes und technischen Ausgaengen in eigenen Laufartefakten.
Offline-Demos sind handgeschrieben und tragen keine Forschungsmetriken.
Menschenratings und der optional token-/livegeschuetzte Zweitmodell-Judge
haben getrennte Artefakte; ein nachtraeglich formulierter Beispielhinweis
ersetzt weder eine Generation noch eine Bewertung.

Die Bloecke A-D untersuchen Stufen 0-4, gemeinsame versus individuelle
Startstrategie, Diagnose-/Regelkontraste, Skriptadaptation und echte allgemeine
Assistentenpolicy. Historische Snippets belegen keine bereits erfolgte
Baseline-Auswahl oder Lernwirkung. Skriptzeit plus Verwirrung ist kein Timer,
vorherbestimmte korrekte Antwort kein Lernerfolg.

Vor Veroeffentlichung oder Weitergabe Arbeitsdateien auf Zugangsdaten,
personenbezogene Eingaben und Nutzungsrechte pruefen. URL-Encoding und TLS
verhindern keine Speicherung von GET-Antwortdaten in Browser-/Server-/Proxylogs;
institutionelles Hosting allein beweist keine Datenschutzkonformitaet.
