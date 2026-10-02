# Ordner `code/data/`

Stand: 2026-10-02. Ablageort der SQLite-Datenbank des Prototyps.
API-/Sitzungsvertrag: [../app/README.md](../app/README.md);
Umgebungsreferenz: [../config/README.md](../config/README.md).

## `tutor.db`

Wird von `app/database.py` beim Serverstart automatisch angelegt
(`initialize_database()` im FastAPI-Lifespan).

### Tabellen

**`chats`** – eine Tutor-Session

| Spalte | Typ | Inhalt |
|---|---|---|
| `chat_id` | TEXT PK | UUID |
| `question_id` | TEXT | zugehörige Aufgabe |
| `stack_context_json` | TEXT | serialisiertes `StackContext` (Pydantic) |
| `current_hint_level` | INTEGER | Aktuelle Stufe `0..MAX_HINT_LEVEL`, Defaultmaximum 4 |
| `baseline_hint_level` | INTEGER | Initiale gewaehlte Stufe neuer Sessions; unabhaengig vom spaeteren Aufstieg |
| `session_state_json` | TEXT | JSON mit Startentscheidung, Antwortzeit, monotonem Uhrwert/Prozess-ID und letzter adaptiver Entscheidung; Default `{}` |
| `created_at` / `updated_at` | TEXT | ISO-UTC-Zeitstempel |

**`messages`** – Nachrichtenverlauf

| Spalte | Typ | Inhalt |
|---|---|---|
| `message_id` | INTEGER PK | Autoincrement |
| `chat_id` | TEXT FK → chats mit `ON DELETE CASCADE` | Session |
| `role` | TEXT | `system`, `user` oder `assistant` |
| `content` | TEXT | Nachrichtentext |
| `created_at` | TEXT | ISO-UTC-Zeitstempel |

Index: `idx_messages_chat` auf `(chat_id, message_id)`.

## Additive Migration

`initialize_database()` prueft vorhandene Spalten. Es ergaenzt fehlendes
`baseline_hint_level` per `ALTER TABLE` und setzt fuer vorhandene Zeilen den
damals aktuellen `current_hint_level` ein. Das ist eine Legacybaseline zum
Migrationszeitpunkt, **keine** rekonstruierte historische Startstufe.
`session_state_json` wird mit `{}` hinzugefuegt. Fruehere Startentscheidungen,
Zeitintervalle, Simulationen oder Diagnosen werden nicht erfunden.

Spaltenerweiterung und Baseline-Backfill laufen gemeinsam in einer expliziten
Transaktion. Bereits vorhandene `NULL`-Legacybaselines aus einer unterbrochenen
Migration werden bei erneuter Initialisierung mit der aktuellen Stufe repariert.
Bekannte nichtleere Baselines bleiben unveraendert.

Neue Chats setzen aktuelle Stufe und Baseline auf die explizite, feste oder
individuell gewaehlte Startstufe; spaetere erfolgreiche Generierungen aendern
nur aktuelle Stufe/Zustand. Fehlgeschlagene Stufenerhoehungen schreiben keinen
Aufstieg. Nutzerfragen koennen bereits gespeichert sein, auch wenn die
Assistantgenerierung scheitert. Einzelne DB-Operationen sind nicht ein
vollstaendiges idempotentes Request-/Retryprotokoll.

Erfolgreiche Antworten speichern `last_response_at` als UTC-Zeitstempel sowie
`last_response_monotonic` und `clock_id` fuer Intervalle nur im selben Prozess.
Nach Neustart/Workerwechsel bleibt das Intervall unbekannt; die gespeicherte
Wallclock ist kein Ersatz. Simulationswerte sind explizite Requestdaten,
keine dauerhaft uebernommene Zeitquelle oder aktive Lernzeitmessung.
Strukturierte Hint-/Hypothesentexte sind serverseitig auf 20000/2000 Zeichen
begrenzt, Auswahlgruende auf 2000; die additive DB-Migration selbst verifiziert
weder diese Modelltexte noch historischen Sessionzustand.

Konfigurationssnapshots, komplette Operationsjournale und Judge-Ratings gehoeren
zu den separaten Evaluationsartefakten, nicht zu neuen vermeintlichen Tabellen
in dieser Datenbank. Gespeichert wird der Hinttext; eine strukturierte
Diagnosehypothese ist ein eigenes JSON-Responsefeld und kein PRT-Ergebnis.

## Hinweise

- Datenbankdateien (`*.db`) sind git-ignoriert, diese README bleibt versioniert.
- Zugriff ausschließlich über `app/chat_store.py` (parameterisierte SQL-Statements).
- SQLite ist für den Prototyp ausreichend, aber **nicht** für hoch-konkurrenten Produktivbetrieb gedacht.
- Pfad ist konfigurierbar über `DATABASE_PATH` (`.env`).
- Vor produktiver Migration Sicherung und Tests auf einer Kopie einplanen;
  keine Tests gegen die echte Nutzerdatenbank ausfuehren.
- Evaluation speichert serverseitig Chats: eine isolierte `DATABASE_PATH`
  verwenden. Clientplanung, Offline-Demo und Artefaktanalyse initialisieren
  keine Tutor-Datenbank.
- Chat-UUIDs bieten keine Authentifizierung. Identitaetspruefung bei
  Chatfortsetzung ersetzt weder Zugriffssteuerung noch mathematische Bewertung.
