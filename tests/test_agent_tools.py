import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.llm.mock_provider import MockLLMProvider
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.system.status import SystemStatusTool
from app.tools.system.time import CurrentTimeTool


@pytest.fixture
def agent() -> JarvisAgent:
    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    registry.register(SystemStatusTool())
    return JarvisAgent(MockLLMProvider(), ToolExecutor(registry))


@pytest.mark.asyncio
async def test_agent_calls_time_tool(agent: JarvisAgent) -> None:
    response = await agent.respond("\uc9c0\uae08 \uba87 \uc2dc\uc57c?")
    assert response.tool_calls[0].name == "get_current_time"
    assert response.tool_calls[0].success is True


@pytest.mark.asyncio
async def test_agent_calls_system_status_tool(agent: JarvisAgent) -> None:
    response = await agent.respond("\uc11c\ubc84 \uc0c1\ud0dc \uc54c\ub824\uc918")
    assert response.tool_calls[0].name == "get_system_status"
    assert response.tool_calls[0].success is True


@pytest.mark.asyncio
async def test_general_chat_does_not_call_tool(agent: JarvisAgent) -> None:
    response = await agent.respond("\uc548\ub155 \uc790\ube44\uc2a4")
    assert response.reply
    assert response.tool_calls == []
