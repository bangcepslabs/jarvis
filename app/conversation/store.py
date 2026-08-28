import asyncio
import logging
from abc import ABC, abstractmethod

from app.conversation.models import ConversationMessage
from app.conversation.sqlite_store import SQLiteConversationRepository

logger = logging.getLogger(__name__)


class ConversationStore(ABC):
    @abstractmethod
    async def append(self, conversation_id: str, message: ConversationMessage) -> None: ...

    @abstractmethod
    async def list_recent(self, conversation_id: str, limit: int | None = None) -> list[ConversationMessage]: ...

    @abstractmethod
    async def clear(self, conversation_id: str) -> None: ...

    @abstractmethod
    async def count(self, conversation_id: str) -> int: ...


class InMemoryConversationStore(ConversationStore):
    def __init__(self, max_messages: int = 50) -> None:
        self._max_messages = max(1, max_messages)
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._lock = asyncio.Lock()

    async def append(self, conversation_id: str, message: ConversationMessage) -> None:
        async with self._lock:
            messages = self._messages.setdefault(conversation_id, [])
            messages.append(message)
            if len(messages) > self._max_messages:
                del messages[:-self._max_messages]
            logger.info("conversation_message_added conversation_id=%s message_count=%s", conversation_id, len(messages))

    async def list_recent(self, conversation_id: str, limit: int | None = None) -> list[ConversationMessage]:
        async with self._lock:
            messages = list(self._messages.get(conversation_id, []))
        return messages[-limit:] if limit is not None else messages

    async def clear(self, conversation_id: str) -> None:
        async with self._lock:
            self._messages.pop(conversation_id, None)
        logger.info("conversation_cleared conversation_id=%s", conversation_id)

    async def count(self, conversation_id: str) -> int:
        async with self._lock:
            return len(self._messages.get(conversation_id, []))


class SQLiteConversationStore(ConversationStore):
    def __init__(self, database_path: str, max_messages: int = 50) -> None:
        self._repository = SQLiteConversationRepository(database_path)

    async def append(self, conversation_id: str, message: ConversationMessage) -> None:
        await asyncio.to_thread(self._repository.append, conversation_id, message)

    async def list_recent(self, conversation_id: str, limit: int | None = None) -> list[ConversationMessage]:
        return await asyncio.to_thread(self._repository.list_recent, conversation_id, limit)

    async def clear(self, conversation_id: str) -> None:
        await asyncio.to_thread(self._repository.clear, conversation_id)

    async def count(self, conversation_id: str) -> int:
        return await asyncio.to_thread(self._repository.count, conversation_id)
