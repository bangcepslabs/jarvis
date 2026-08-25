from abc import ABC, abstractmethod
from typing import Any

from app.memory.models import MemoryEntry


class MemoryStore(ABC):
    @abstractmethod
    async def save(self, entry: MemoryEntry) -> MemoryEntry: ...

    @abstractmethod
    async def get(self, memory_id: int) -> MemoryEntry | None: ...

    @abstractmethod
    async def update(self, entry: MemoryEntry) -> MemoryEntry: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]: ...

    @abstractmethod
    async def delete(self, memory_id: int) -> bool: ...

    @abstractmethod
    async def list(self, limit: int = 100) -> list[MemoryEntry]: ...
