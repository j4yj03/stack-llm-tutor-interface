import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from app.config import MAX_HINT_LEVEL
from app.database import get_connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_chat_id(chat_id: str) -> str:
    try:
        return str(UUID(chat_id))
    except (ValueError, TypeError) as exc:
        raise ValueError("Ungültige chat_id") from exc


class ChatStore:
    def __init__(
        self,
        database_path: Optional[Path] = None
    ) -> None:
        self.database_path = database_path

    def create_chat(
        self,
        question_id: str,
        stack_context: Dict,
        hint_level: int = 1
    ) -> str:
        if not 1 <= hint_level <= MAX_HINT_LEVEL:
            raise ValueError("Ungültige Hilfestufe")

        chat_id = str(uuid4())
        now = utc_now()
        connection = get_connection(self.database_path)

        try:
            connection.execute(
                """
                INSERT INTO chats (
                    chat_id,
                    question_id,
                    stack_context_json,
                    current_hint_level,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    question_id,
                    json.dumps(
                        stack_context,
                        ensure_ascii=False
                    ),
                    hint_level,
                    now,
                    now
                )
            )
            connection.commit()
        finally:
            connection.close()

        return chat_id

    def get_chat(
        self,
        chat_id: str
    ) -> Optional[Dict]:
        chat_id = validate_chat_id(chat_id)
        connection = get_connection(self.database_path)

        try:
            row = connection.execute(
                """
                SELECT *
                FROM chats
                WHERE chat_id = ?
                """,
                (chat_id,)
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return {
            "chat_id": row["chat_id"],
            "question_id": row["question_id"],
            "stack_context": json.loads(
                row["stack_context_json"]
            ),
            "current_hint_level": row[
                "current_hint_level"
            ],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str
    ) -> None:
        chat_id = validate_chat_id(chat_id)

        if role not in {
            "system",
            "user",
            "assistant"
        }:
            raise ValueError(
                "Ungültige Nachrichtenrolle"
            )

        if not content.strip():
            raise ValueError(
                "Nachrichteninhalt darf nicht leer sein"
            )

        now = utc_now()
        connection = get_connection(self.database_path)

        try:
            chat_exists = connection.execute(
                """
                SELECT 1
                FROM chats
                WHERE chat_id = ?
                """,
                (chat_id,)
            ).fetchone()

            if chat_exists is None:
                raise KeyError("Chat nicht gefunden")

            connection.execute(
                """
                INSERT INTO messages (
                    chat_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    chat_id,
                    role,
                    content,
                    now
                )
            )

            connection.execute(
                """
                UPDATE chats
                SET updated_at = ?
                WHERE chat_id = ?
                """,
                (now, chat_id)
            )

            connection.commit()
        finally:
            connection.close()

    def get_messages(
        self,
        chat_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        chat_id = validate_chat_id(chat_id)
        connection = get_connection(self.database_path)

        try:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT role, content, created_at
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY message_id ASC
                    """,
                    (chat_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT role, content, created_at
                    FROM (
                        SELECT message_id,
                               role,
                               content,
                               created_at
                        FROM messages
                        WHERE chat_id = ?
                        ORDER BY message_id DESC
                        LIMIT ?
                    )
                    ORDER BY message_id ASC
                    """,
                    (chat_id, limit)
                ).fetchall()
        finally:
            connection.close()

        return [
            {
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]

    def set_hint_level(
        self,
        chat_id: str,
        hint_level: int
    ) -> None:
        chat_id = validate_chat_id(chat_id)

        if not 1 <= hint_level <= MAX_HINT_LEVEL:
            raise ValueError("Ungültige Hilfestufe")

        connection = get_connection(self.database_path)

        try:
            cursor = connection.execute(
                """
                UPDATE chats
                SET current_hint_level = ?,
                    updated_at = ?
                WHERE chat_id = ?
                """,
                (
                    hint_level,
                    utc_now(),
                    chat_id
                )
            )

            if cursor.rowcount == 0:
                raise KeyError("Chat nicht gefunden")

            connection.commit()
        finally:
            connection.close()

    def next_hint_level(
        self,
        chat_id: str
    ) -> int:
        chat = self.get_chat(chat_id)

        if chat is None:
            raise KeyError("Chat nicht gefunden")

        next_level = min(
            chat["current_hint_level"] + 1,
            MAX_HINT_LEVEL
        )

        self.set_hint_level(
            chat_id,
            next_level
        )

        return next_level