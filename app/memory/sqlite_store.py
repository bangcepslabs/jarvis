import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.memory.models import MemoryCategory, MemoryEntry, MemorySource
from app.memory.base import MemoryStore


class SQLiteMemoryStore(MemoryStore):
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    memory_key TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                    ,source TEXT NOT NULL DEFAULT 'explicit'
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(memories)").fetchall()}
            if "source" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'explicit'")

    @staticmethod
    def _entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"], category=MemoryCategory(row["category"]), key=row["memory_key"], content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
            source=MemorySource(row["source"]) if "source" in row.keys() else MemorySource.EXPLICIT,
        )

    async def save(self, entry: MemoryEntry) -> MemoryEntry:
        return await asyncio.to_thread(self._save, entry)

    def _save(self, entry: MemoryEntry) -> MemoryEntry:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO memories(category, memory_key, content, created_at, updated_at, source)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(memory_key) DO UPDATE SET category=excluded.category, content=excluded.content, updated_at=excluded.updated_at, source=excluded.source""",
                (entry.category.value, entry.key, entry.content, entry.created_at.isoformat(), now, entry.source.value),
            )
            row = connection.execute("SELECT * FROM memories WHERE memory_key = ?", (entry.key,)).fetchone()
        return self._entry(row)

    async def get(self, memory_id: int) -> MemoryEntry | None:
        return await asyncio.to_thread(self._get, memory_id)

    def _get(self, memory_id: int) -> MemoryEntry | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._entry(row) if row else None

    async def update(self, entry: MemoryEntry) -> MemoryEntry:
        return await self.save(entry)

    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        return await asyncio.to_thread(self._search, query, limit)

    def _search(self, query: str, limit: int) -> list[MemoryEntry]:
        terms = [term for term in query.casefold().split() if len(term) >= 2][:8]
        if not terms:
            return []
        clauses = " OR ".join("LOWER(memory_key) LIKE ? OR LOWER(content) LIKE ?" for _ in terms)
        params = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM memories WHERE {clauses} ORDER BY updated_at DESC LIMIT ?", (*params, limit)).fetchall()
        return [self._entry(row) for row in rows]

    async def delete(self, memory_id: int) -> bool:
        return await asyncio.to_thread(self._delete, memory_id)

    def _delete(self, memory_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    async def list(self, limit: int = 100) -> list[MemoryEntry]:
        return await asyncio.to_thread(self._list, limit)

    def _list(self, limit: int) -> list[MemoryEntry]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._entry(row) for row in rows]
