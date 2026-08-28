import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.conversation.models import ConversationMessage


class SQLiteConversationRepository:
    """Small SQLite repository shared by conversation and summary stores."""

    _roles = {"system", "user", "assistant", "tool"}

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._write_lock, self._connect() as connection:
            if self.database_path != ":memory:":
                connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT,
                    summary_updated_at TEXT,
                    summarized_through_sequence INTEGER NOT NULL DEFAULT 0,
                    summary_keys TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT,
                    tool_name TEXT,
                    tool_call_id TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(conversation_id, sequence),
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_conversation_messages_order
                    ON conversation_messages(conversation_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                    ON conversations(updated_at);
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def append(self, conversation_id: str, message: ConversationMessage) -> None:
        now = self._now()
        with self._write_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO conversations(id, created_at, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at",
                (conversation_id, now, now),
            )
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO conversation_messages(
                    conversation_id, sequence, role, content, message_type,
                    tool_name, tool_call_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, sequence, message.role, message.content, message.role,
                 message.tool_name, message.tool_call_id, message.created_at.isoformat()),
            )

    def list_recent(self, conversation_id: str, limit: int | None = None) -> list[ConversationMessage]:
        query = "SELECT role, content, tool_name, tool_call_id, created_at, sequence FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence"
        params: tuple[object, ...] = (conversation_id,)
        if limit is not None:
            query = "SELECT role, content, tool_name, tool_call_id, created_at, sequence FROM (SELECT role, content, tool_name, tool_call_id, created_at, sequence FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence DESC LIMIT ?) ORDER BY sequence"
            params = (conversation_id, limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        messages: list[ConversationMessage] = []
        for row in rows:
            if not self._valid_row(row):
                continue
            try:
                messages.append(self._message(row))
            except (TypeError, ValueError):
                continue
        return messages

    def count(self, conversation_id: str) -> int:
        with self._connect() as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()[0])

    def clear(self, conversation_id: str) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def get_summary(self, conversation_id: str):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT summary, summary_updated_at, summarized_through_sequence, summary_keys FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        if not row or not row["summary"]:
            return None
        return row

    def save_summary(self, conversation_id: str, text: str, summarized_keys: set[str]) -> None:
        now = self._now()
        with self._write_lock, self._connect() as connection:
            cursor = self._summary_cursor(connection, conversation_id, summarized_keys)
            connection.execute(
                "INSERT INTO conversations(id, created_at, updated_at, summary, summary_updated_at, summarized_through_sequence, summary_keys) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET summary=excluded.summary, summary_updated_at=excluded.summary_updated_at, "
                "summarized_through_sequence=excluded.summarized_through_sequence, summary_keys=excluded.summary_keys",
                (conversation_id, now, now, text, now, cursor, json.dumps(sorted(summarized_keys))),
            )

    @staticmethod
    def _summary_cursor(connection: sqlite3.Connection, conversation_id: str, keys: set[str]) -> int:
        if not keys:
            return 0
        rows = connection.execute(
            "SELECT sequence, role, content, tool_name, tool_call_id, created_at FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence",
            (conversation_id,),
        ).fetchall()
        groups: list[list[sqlite3.Row]] = []
        current: list[sqlite3.Row] = []
        for row in rows:
            if row["role"] == "user" and current:
                groups.append(current)
                current = []
            current.append(row)
        if current:
            groups.append(current)
        cursor = 0
        for group in groups:
            payload = "\n".join(
                f"{row['role']}|{row['created_at']}|{row['tool_name']}|{row['tool_call_id']}|{row['content']}"
                for row in group
            )
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() in keys:
                cursor = max(cursor, int(group[-1]["sequence"]))
        return cursor

    @classmethod
    def _valid_row(cls, row: sqlite3.Row) -> bool:
        return row["role"] in cls._roles

    @staticmethod
    def _message(row: sqlite3.Row) -> ConversationMessage:
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return ConversationMessage(
            role=row["role"], content=row["content"], created_at=created_at,
            tool_name=row["tool_name"], tool_call_id=row["tool_call_id"],
        )

    @staticmethod
    def summary_state(row: sqlite3.Row):
        from app.conversation.summary import ConversationSummaryState

        try:
            keys = frozenset(json.loads(row["summary_keys"] or "[]"))
        except (TypeError, ValueError):
            keys = frozenset()
        updated_at = datetime.fromisoformat(row["summary_updated_at"])
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return ConversationSummaryState(row["summary"], keys, updated_at)
