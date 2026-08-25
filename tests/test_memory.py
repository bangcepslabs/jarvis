import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.memory.models import MemoryCategory
from app.memory.service import MemoryService
from app.memory.sqlite_store import SQLiteMemoryStore
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class ContextProvider(LLMProvider):
    def __init__(self) -> None:
        self.messages = []

    async def chat(self, messages, tools=None):
        self.messages = messages
        return LLMResponse(content="context received")


def phrase(*code_points: int) -> str:
    return "".join(chr(code_point) for code_point in code_points)


@pytest.mark.asyncio
async def test_sqlite_memory_persists_and_updates_by_key(tmp_path) -> None:
    path = str(tmp_path / "memory.db")
    first = SQLiteMemoryStore(path)
    service = MemoryService(first)
    saved = await service.save_memory(MemoryCategory.ENVIRONMENT, "main_server_name", "home-jarvis")
    assert saved is not None
    updated = await service.save_memory(MemoryCategory.ENVIRONMENT, "main_server_name", "jarvis-main")
    assert updated.content == "jarvis-main"
    second = SQLiteMemoryStore(path)
    entries = await second.search("main_server_name")
    assert len(entries) == 1
    assert entries[0].content == "jarvis-main"


@pytest.mark.asyncio
async def test_memory_delete_and_search(tmp_path) -> None:
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    await service.save_memory(MemoryCategory.FACT, "favorite_editor", "vim")
    assert len(await service.search_memories("favorite_editor")) == 1
    assert await service.delete_memory("favorite_editor") == 1
    assert await service.search_memories("favorite_editor") == []


@pytest.mark.asyncio
async def test_agent_explicit_memory_save_and_retrieval_context(tmp_path) -> None:
    memory = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    provider = ContextProvider()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), memory_service=memory)
    save_message = phrase(0xB0B4, 0x20, 0xBA54, 0xC778, 0x20, 0xC11C, 0xBC84, 0x20, 0xC774, 0xB984, 0xC740) + " home-jarvis" + phrase(0xC774, 0xB2E4, 0xB77C, 0xACE0, 0x20, 0xAE30, 0xC5B5, 0xD574, 0xC918)
    saved = await agent.respond(save_message)
    assert saved.reply == "Memory saved."
    query = phrase(0xB0B4, 0x20, 0xBA54, 0xC778, 0x20, 0xC11C, 0xBC84, 0x20, 0xC774, 0xB984, 0x20, 0xBB50, 0xC600, 0xC9C0)
    await agent.respond(query)
    context_messages = [message.content for message in provider.messages if "Relevant long-term memory" in message.content]
    assert context_messages
    assert "home-jarvis" in context_messages[0]


@pytest.mark.asyncio
async def test_memory_command_update_and_delete(tmp_path) -> None:
    memory = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    provider = ContextProvider()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), memory_service=memory)
    await memory.save_memory(MemoryCategory.ENVIRONMENT, "main_server_name", "home-jarvis")
    update_message = phrase(0xBA54, 0xC778, 0x20, 0xC11C, 0xBC84, 0x20, 0xC774, 0xB984) + " jarvis-main " + phrase(0xAE30, 0xC5B5, 0xD574, 0xC918)
    assert (await agent.respond(update_message)).reply == "Memory saved."
    assert (await memory.search_memories("main_server_name"))[0].content == "jarvis-main"
    delete_message = phrase(0xBA54, 0xC778, 0x20, 0xC11C, 0xBC84, 0x20, 0xC774, 0xB984) + " " + phrase(0xC9C0, 0xC6B0, 0xC9C0, 0xB9C8)
    assert (await agent.respond(delete_message)).reply == "Memory deleted."


@pytest.mark.asyncio
async def test_secret_memory_is_rejected(tmp_path) -> None:
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    assert await service.save_memory(MemoryCategory.OTHER, "api_key", "secret-value") is None


@pytest.mark.asyncio
async def test_api_key_phrase_is_rejected(tmp_path) -> None:
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    assert await service.save_memory(MemoryCategory.OTHER, "api_key", "sk-test-1234") is None
