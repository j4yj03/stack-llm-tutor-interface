# Ordner `code/data/`

Ablageort der SQLite-Datenbank des Prototyps.

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
| `current_hint_level` | INTEGER | aktuelle Stufe (1–4) |
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

## Hinweise

- Diese Datei ist via `.gitignore` (`*.db`) vom Commit ausgeschlossen.
- Zugriff ausschließlich über `app/chat_store.py` (parameterisierte SQL-Statements).
- SQLite ist für den Prototyp ausreichend, aber **nicht** für hoch-konkurrenten Produktivbetrieb gedacht.
- Pfad ist konfigurierbar über `DATABASE_PATH` (`.env`).
- Ein Schemawechsel nach echten Nutzerdaten erfordert eine explizite Migration.
