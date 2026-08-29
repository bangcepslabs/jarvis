import asyncio
import re
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
                    ,source TEXT NOT NULL DEFAULT 'explicit',
                    importance REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    last_used_at TEXT,
                    use_count INTEGER NOT NULL DEFAULT 0
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(memories)").fetchall()}
            if "source" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'explicit'")
            migrations = {
                "importance": "ALTER TABLE memories ADD COLUMN importance REAL NOT NULL DEFAULT 0.5",
                "confidence": "ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0",
                "last_used_at": "ALTER TABLE memories ADD COLUMN last_used_at TEXT",
                "use_count": "ALTER TABLE memories ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

    @staticmethod
    def _entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"], category=MemoryCategory(row["category"]), key=row["memory_key"], content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
            source=MemorySource(row["source"]) if "source" in row.keys() else MemorySource.EXPLICIT,
            importance=row["importance"] if "importance" in row.keys() else 0.5,
            confidence=row["confidence"] if "confidence" in row.keys() else 1.0,
            last_used_at=datetime.fromisoformat(row["last_used_at"]) if row["last_used_at"] else None,
            use_count=row["use_count"] if "use_count" in row.keys() else 0,
        )

    async def save(self, entry: MemoryEntry) -> MemoryEntry:
        return await asyncio.to_thread(self._save, entry)

    def _save(self, entry: MemoryEntry) -> MemoryEntry:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO memories(category, memory_key, content, created_at, updated_at, source, importance, confidence, last_used_at, use_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(memory_key) DO UPDATE SET category=excluded.category, content=excluded.content, updated_at=excluded.updated_at, source=excluded.source, importance=excluded.importance, confidence=excluded.confidence""",
                (entry.category.value, entry.key, entry.content, entry.created_at.isoformat(), now, entry.source.value, entry.importance, entry.confidence, entry.last_used_at.isoformat() if entry.last_used_at else None, entry.use_count),
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
        terms = list(self._tokens(query))[:12]
        if not terms:
            return []
        clauses = " OR ".join("LOWER(memory_key) LIKE ? OR LOWER(content) LIKE ? OR LOWER(category) LIKE ?" for _ in terms)
        params = [value for term in terms for value in (f"%{term}%", f"%{term}%", f"%{term}%")]
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM memories WHERE {clauses}", params).fetchall()
        query_terms = set(terms)
        ranked = []
        now = datetime.now(UTC)
        for row in rows:
            key_terms = self._tokens(row["memory_key"])
            content_terms = self._tokens(row["content"])
            category_terms = self._tokens(row["category"])
            key_overlap = len(query_terms & key_terms)
            overlap = len(query_terms & (key_terms | content_terms | category_terms))
            if overlap == 0:
                continue
            updated = datetime.fromisoformat(row["updated_at"])
            age_days = max(0.0, (now - updated).total_seconds() / 86400)
            recency = 0.2 / (1 + age_days / 30)
            usage_recency = 0.1 / (1 + max(0.0, (now - datetime.fromisoformat(row["last_used_at"])).total_seconds()) / 86400) if row["last_used_at"] else 0.0
            score = overlap + key_overlap * 1.5 + recency + float(row["importance"]) * 0.25 + usage_recency
            if row["source"] == MemorySource.EXPLICIT.value:
                score += 0.05
            ranked.append((score, row["updated_at"], row))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [self._entry(row) for _, _, row in ranked[: max(0, limit)]]

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {token.casefold() for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE) if len(token) >= 2}

    async def delete(self, memory_id: int) -> bool:
        return await asyncio.to_thread(self._delete, memory_id)

    def _delete(self, memory_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    async def mark_used(self, memory_ids: list[int]) -> None:
        if memory_ids:
            await asyncio.to_thread(self._mark_used, memory_ids)

    def _mark_used(self, memory_ids: list[int]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.executemany("UPDATE memories SET last_used_at = ?, use_count = use_count + 1 WHERE id = ?", [(now, memory_id) for memory_id in memory_ids])

    async def list(self, limit: int = 100) -> list[MemoryEntry]:
        return await asyncio.to_thread(self._list, limit)

    def _list(self, limit: int) -> list[MemoryEntry]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._entry(row) for row in rows]
