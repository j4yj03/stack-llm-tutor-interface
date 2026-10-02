import sqlite3
from pathlib import Path
from typing import Optional

from app.config import DATABASE_PATH


def get_connection(
    database_path: Optional[Path] = None
) -> sqlite3.Connection:
    path = database_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(path),
        check_same_thread=False
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(
    database_path: Optional[Path] = None
) -> None:
    connection = get_connection(database_path)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL,
                stack_context_json TEXT NOT NULL,
                current_hint_level INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(chat_id)
                    REFERENCES chats(chat_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_messages_chat
            ON messages(chat_id, message_id);
            """
        )
        # Explicit additive migration for already persisted prototype sessions.
        connection.execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(chats)")}
        if "baseline_hint_level" not in columns:
            connection.execute("ALTER TABLE chats ADD COLUMN baseline_hint_level INTEGER")
        connection.execute("UPDATE chats SET baseline_hint_level=current_hint_level WHERE baseline_hint_level IS NULL")
        if "session_state_json" not in columns:
            connection.execute("ALTER TABLE chats ADD COLUMN session_state_json TEXT NOT NULL DEFAULT '{}'")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
