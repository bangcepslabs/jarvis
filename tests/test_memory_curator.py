import pytest

from app.core.config import Settings
from app.llm.models import LLMResponse
from app.memory.curator import MemoryCurator, memory_decision_response_schema
from app.memory.models import MemoryAction, MemoryCategory, MemoryDecision, MemorySource
from app.memory.service import MemoryService
from app.memory.sqlite_store import SQLiteMemoryStore


class DecisionProvider:
    def __init__(self, content: str):
        self.content = content
        self.messages = []

    async def chat(self, messages, **kwargs):
        self.messages.append(messages)
        return LLMResponse(content=self.content)


class FailingProvider:
    async def chat(self, messages, **kwargs):
        raise TimeoutError("simulated curator timeout")


@pytest.mark.asyncio
async def test_curator_parses_strict_decision(tmp_path):
    provider = DecisionProvider('{"action":"SAVE","category":"preference","key":"reply_style","value":"짧게 답해","reason":"durable","importance":0.8,"confidence":0.9}')
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    decision = await MemoryCurator(provider, service, Settings(llm_model="test")).curate("짧게 답해줘", "알겠어")
    assert decision and decision.action == MemoryAction.SAVE
    assert len(provider.messages) == 1
    assert len(provider.messages[0]) == 1


@pytest.mark.asyncio
async def test_curator_parses_nullable_scores_and_skip_decision(tmp_path):
    provider = DecisionProvider('{"action":"IGNORE","category":null,"key":null,"value":null,"reason":"casual","importance":null,"confidence":null}')
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    decision = await MemoryCurator(provider, service, Settings(llm_model="test")).curate("hello", "hi")
    assert decision and decision.action == MemoryAction.IGNORE
    assert decision.importance is None and decision.confidence is None


def test_memory_decision_schema_requires_every_property_and_allows_null_scores():
    schema = memory_decision_response_schema()["json_schema"]["schema"]
    properties = schema["properties"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(properties)
    assert properties["importance"]["type"] == ["number", "null"]
    assert properties["confidence"]["type"] == ["number", "null"]


def test_memory_decision_accepts_null_scores():
    decision = MemoryDecision.model_validate({
        "action": "IGNORE", "category": None, "key": None, "value": None,
        "reason": "casual", "importance": None, "confidence": None,
    })
    assert decision.importance is None
    assert decision.confidence is None


@pytest.mark.asyncio
async def test_curator_invalid_json_is_best_effort(tmp_path):
    provider = DecisionProvider("not-json")
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    assert await MemoryCurator(provider, service, Settings(llm_model="test")).curate("hi", "hello") is None


@pytest.mark.asyncio
async def test_curator_timeout_is_isolated(tmp_path):
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    settings = Settings(llm_model="test", memory_curator_timeout_seconds=0.01)
    assert await MemoryCurator(FailingProvider(), service, settings).curate("hi", "hello") is None


@pytest.mark.asyncio
async def test_adaptive_memory_deduplicates_updates_and_blocks_secret(tmp_path):
    service = MemoryService(SQLiteMemoryStore(str(tmp_path / "memory.db")))
    saved = await service.apply_decision(MemoryDecision(action="SAVE", category=MemoryCategory.PREFERENCE, key="style", value="concise"))
    assert saved and saved.source == MemorySource.ADAPTIVE
    assert await service.apply_decision(MemoryDecision(action="SAVE", category=MemoryCategory.PREFERENCE, key="style2", value="concise")) is None
    updated = await service.apply_decision(MemoryDecision(action="UPDATE", category=MemoryCategory.PREFERENCE, key="style", value="detailed"))
    assert updated and updated.content == "detailed"
    assert await service.apply_decision(MemoryDecision(action="SAVE", category=MemoryCategory.OTHER, key="api_key", value="secret-value")) is None
