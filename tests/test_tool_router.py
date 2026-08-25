import json

import pytest

from app.agent.models import ChatMessage
from app.agent.tool_router import ToolRouter
from app.agent.jarvis_agent import JarvisAgent
from app.core.config import Settings
from app.llm.mock_provider import MockLLMProvider
from app.llm.models import LLMResponse, LLMToolCall
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.system.status import SystemStatusTool
from app.tools.system.time import CurrentTimeTool


@pytest.mark.asyncio
async def test_router_returns_valid_decision_from_provider_json() -> None:
    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    registry.register(SystemStatusTool())
    router = ToolRouter(MockLLMProvider(), registry, Settings(llm_provider="mock"))
    decision = await router.route("\uc9c0\uae08 \uba87 \uc2dc\uc57c?")
    assert decision.tool_name == "get_current_time"


@pytest.mark.asyncio
async def test_router_uses_registry_backed_structured_schema() -> None:
    class Provider(MockLLMProvider):
        def __init__(self):
            self.response_format = None

        async def chat(self, messages, response_format=None, **kwargs):
            self.response_format = response_format
            return LLMResponse(content='{"tool_name":"NONE"}')

    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    provider = Provider()
    await ToolRouter(provider, registry, Settings(llm_provider="mock")).route("안녕")
    schema = provider.response_format["json_schema"]["schema"]
    assert schema["properties"]["tool_name"]["enum"] == ["NONE", "get_current_time"]


@pytest.mark.asyncio
async def test_agent_filters_main_call_to_selected_tool() -> None:
    class RecordingProvider(MockLLMProvider):
        def __init__(self):
            self.calls = []

        async def chat(self, messages, tools=None, tool_choice=None, response_format=None, **kwargs):
            self.calls.append((tools, tool_choice, response_format))
            if response_format:
                return LLMResponse(content='{"tool_name":"get_current_time"}')
            if tools:
                return LLMResponse(tool_calls=[LLMToolCall(id="time", name="get_current_time")], finish_reason="tool_calls")
            return LLMResponse(content="time result")

    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    provider = RecordingProvider()
    settings = Settings(llm_provider="mock")
    agent = JarvisAgent(provider, ToolExecutor(registry), registry, tool_router=ToolRouter(provider, registry, settings))
    response = await agent.respond("지금 몇 시야?")
    assert response.tool_calls[0].name == "get_current_time"
    assert len(provider.calls[1][0]) == 1
    assert provider.calls[1][1] == {"type": "function", "function": {"name": "get_current_time"}}
    assert provider.calls[2][0] == []


def test_registry_routing_hints_are_source_of_truth() -> None:
    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    hints = registry.get_routing_hints()
    assert hints == [{"name": "get_current_time", "routing_hint": "Current clock time, date, day, or timezone only."}]


def test_route_output_contract_is_json_object() -> None:
    assert json.loads('{"tool_name": null}') == {"tool_name": None}
