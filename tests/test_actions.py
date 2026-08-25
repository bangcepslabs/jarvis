from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from app.actions.models import ActionAuthorization, ActionStatus
from app.actions.service import ActionConfirmationService
from app.agent.jarvis_agent import JarvisAgent
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, LLMToolCall
from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.docker.models import ContainerArguments
from app.tools.docker.restart import RestartContainerTool
from app.tools.executor import ToolExecutor
from app.tools.models import ToolResult
from app.tools.registry import ToolRegistry


class FakeRestartProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(tool_calls=[LLMToolCall(name="restart_container", arguments={"container": "pulse-api"})])
        return LLMResponse(content="final")


class CountingDockerService:
    def __init__(self) -> None:
        self.restart_count = 0

    def restart_container(self, container: str, timeout: int = 10):
        self.restart_count += 1
        return {"container": container, "status": "running", "restarted": True}


def build_agent(ttl: int = 300):
    service = CountingDockerService()
    registry = ToolRegistry()
    registry.register(RestartContainerTool(service))
    actions = ActionConfirmationService(ttl_seconds=ttl)
    executor = ToolExecutor(registry)
    provider = FakeRestartProvider()
    return JarvisAgent(provider, executor, registry, actions), service, actions


@pytest.mark.asyncio
async def test_write_request_creates_pending_without_execution() -> None:
    agent, service, _ = build_agent()
    response = await agent.respond("restart pulse-api")
    assert response.pending_action is not None
    assert service.restart_count == 0


@pytest.mark.asyncio
async def test_approval_executes_restart_once() -> None:
    agent, service, actions = build_agent()
    response = await agent.respond("restart pulse-api")
    action_id = response.pending_action.id
    approved = await agent.respond("yes")
    assert approved.tool_calls[0].success is True
    assert service.restart_count == 1
    assert (await actions.get_action(action_id)).status == ActionStatus.EXECUTED
    again = await agent.respond("yes")
    assert service.restart_count == 1
    assert "no action" in again.reply.casefold()


@pytest.mark.asyncio
async def test_rejection_does_not_execute_and_cannot_be_reapproved() -> None:
    agent, service, actions = build_agent()
    response = await agent.respond("restart pulse-api")
    action_id = response.pending_action.id
    rejected = await agent.respond("cancel")
    assert "cancelled" in rejected.reply.casefold()
    assert service.restart_count == 0
    assert (await actions.get_action(action_id)).status == ActionStatus.REJECTED
    assert (await actions.approve_action(action_id)) is None


@pytest.mark.asyncio
async def test_expired_action_cannot_be_approved() -> None:
    agent, service, _ = build_agent(ttl=-1)
    response = await agent.respond("restart pulse-api")
    expired = await agent.respond("yes")
    assert "expired" in expired.reply.casefold()
    assert service.restart_count == 0


@pytest.mark.asyncio
async def test_second_write_request_is_blocked_while_pending() -> None:
    agent, _, _ = build_agent()
    first = await agent.respond("restart pulse-api")
    second = await agent.respond("restart postgres")
    assert first.pending_action is not None
    assert second.pending_action is not None
    assert "awaiting confirmation" in second.reply.casefold()


@pytest.mark.asyncio
async def test_dangerous_tool_is_denied_even_with_authorization() -> None:
    class DangerousTool(JarvisTool):
        name = "dangerous_test"
        description = "test"
        safety_level = ToolSafetyLevel.DANGEROUS

        async def execute(self, arguments: BaseModel) -> ToolResult:
            return ToolResult(success=True, tool_name=self.name)

    registry = ToolRegistry()
    registry.register(DangerousTool())
    result = await ToolExecutor(registry).execute(
        "dangerous_test",
        {},
        ActionAuthorization(action_id="act_test", tool_name="dangerous_test", approved_at=datetime.now(UTC)),
    )
    assert result.success is False


def test_write_arguments_cannot_include_confirmation_flags() -> None:
    with pytest.raises(ValueError):
        ContainerArguments.model_validate({"container": "pulse-api", "confirmed": True})
