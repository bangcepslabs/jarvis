import logging
import pytest
from pydantic import BaseModel, Field

from app.agent.jarvis_agent import JarvisAgent
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, LLMToolCall
from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.executor import ToolExecutor
from app.tools.models import ToolResult
from app.tools.registry import ToolRegistry


class FakeProvider(LLMProvider):
    def __init__(self, call: LLMToolCall, final: str = "Final answer from tool data.") -> None:
        self.call = call
        self.final = final
        self.requests: list[list[object]] = []

    async def chat(self, messages, tools=None):
        self.requests.append(messages)
        if len(self.requests) == 1:
            return LLMResponse(tool_calls=[self.call], finish_reason="tool_calls")
        return LLMResponse(content=self.final)


class RequiredArguments(BaseModel):
    value: int = Field(gt=0)


class RequiredTool(JarvisTool):
    name = "required_tool"
    description = "A validation test tool."
    arguments_model = RequiredArguments

    async def execute(self, arguments: RequiredArguments) -> ToolResult:
        return ToolResult(success=True, tool_name=self.name, data={"value": arguments.value})


class FailingTool(JarvisTool):
    name = "failing_tool"
    description = "A failure test tool."

    async def execute(self, arguments: BaseModel) -> ToolResult:
        raise RuntimeError("internal failure")


def _agent(provider: LLMProvider, tool: JarvisTool) -> JarvisAgent:
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)
    return JarvisAgent(provider, executor, registry)


@pytest.mark.asyncio
async def test_native_tool_call_executes_and_feeds_result_back(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="app.agent.jarvis_agent")
    provider = FakeProvider(LLMToolCall(id="1", name="required_tool", arguments={"value": 3}))
    response = await _agent(provider, RequiredTool()).respond("컴퓨터가 바빠?")
    assert response.reply == "Final answer from tool data."
    assert response.tool_calls[0].success is True
    assert any(
        message.role == "system" and "TOOL RESULT PRESENTATION" in message.content
        for message in provider.requests[1]
    )
    assert provider.requests[1][-1].role == "tool"
    assert '"success": true' in provider.requests[1][-1].content
    assert '"value": 3' in provider.requests[1][-1].content
    assert "stage=main_llm_raw" in caplog.text
    assert "stage=tool_final_llm_raw" in caplog.text
    assert "stage=final_user_response" in caplog.text


@pytest.mark.asyncio
async def test_unknown_tool_is_not_executed() -> None:
    provider = FakeProvider(LLMToolCall(id="1", name="delete_everything"))
    response = await _agent(provider, RequiredTool()).respond("do it")
    assert response.tool_calls[0].success is False
    assert "Final answer" in response.reply


@pytest.mark.asyncio
async def test_invalid_arguments_are_rejected_before_tool_execution() -> None:
    provider = FakeProvider(LLMToolCall(id="1", name="required_tool", arguments={"value": -1}))
    response = await _agent(provider, RequiredTool()).respond("run")
    assert response.tool_calls[0].success is False


@pytest.mark.asyncio
async def test_tool_exception_becomes_safe_result() -> None:
    provider = FakeProvider(LLMToolCall(id="1", name="failing_tool"), final="The requested information could not be retrieved.")
    response = await _agent(provider, FailingTool()).respond("run")
    assert response.tool_calls[0].success is False
    assert "could not be retrieved" in response.reply


@pytest.mark.asyncio
async def test_write_tool_requested_by_llm_is_denied() -> None:
    class WriteTool(RequiredTool):
        name = "write_tool"
        safety_level = ToolSafetyLevel.WRITE

    provider = FakeProvider(LLMToolCall(id="1", name="write_tool"))
    response = await _agent(provider, WriteTool()).respond("change it")
    assert response.tool_calls[0].success is False
