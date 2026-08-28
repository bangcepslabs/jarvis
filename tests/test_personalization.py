from types import SimpleNamespace

import pytest

from app.agent.prompt import build_system_prompt, infer_conversation_style
from app.memory.models import MemoryCategory
from app.memory.service import MemoryService
from app.memory.sqlite_store import SQLiteMemoryStore


def message(role: str, content: str):
    return SimpleNamespace(role=role, content=content)


def test_style_adapts_to_recent_technical_conversation():
    style = infer_conversation_style([message("user", "Please explain this Python API stack trace")])
    assert style.name == "technical"
    assert "technical" in build_system_prompt(style=style)


def test_voice_prompt_is_short_and_conclusion_first():
    prompt = build_system_prompt("voice")
    assert "VOICE RESPONSE MODE" in prompt
    assert "1–3 short sentences" in prompt
    assert "Explicit requests" in prompt


def test_text_prompt_does_not_include_voice_policy():
    assert "VOICE RESPONSE MODE" not in build_system_prompt("text")


@pytest.mark.asyncio
async def test_memory_search_ranks_relevant_key_and_excludes_irrelevant(tmp_path):
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    await service.save_memory(MemoryCategory.ENVIRONMENT, "main_server_name", "jarvis-main")
    await service.save_memory(MemoryCategory.PREFERENCE, "coffee", "dark roast")

    results = await service.search_memories("What is the main server name?")
    assert [item.key for item in results] == ["main_server_name"]


@pytest.mark.asyncio
async def test_memory_retrieval_has_a_small_budget(tmp_path):
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")), max_context_items=2)
    for index in range(5):
        await service.save_memory(MemoryCategory.FACT, f"fact_{index}", "shared project context")
    assert len(await service.search_memories("shared project context")) == 2
