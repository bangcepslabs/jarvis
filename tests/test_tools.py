import pytest
from pydantic import BaseModel

from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.executor import ToolExecutor
from app.tools.models import ToolResult
from app.tools.registry import ToolRegistry
from app.tools.system.status import SystemStatusTool
from app.tools.system.time import CurrentTimeTool


class DummyWriteTool(JarvisTool):
    name = "dummy_write"
    description = "Test-only state-changing tool."
    safety_level = ToolSafetyLevel.WRITE

    async def execute(self, arguments: BaseModel) -> ToolResult:
        return ToolResult(success=True, tool_name=self.name)


def test_registry_registers_and_gets_tools() -> None:
    registry = ToolRegistry()
    tool = CurrentTimeTool()
    registry.register(tool)
    assert registry.get(tool.name) is tool
    assert registry.get("missing") is None
    assert registry.get_available_tools()[0]["name"] == tool.name


def test_registry_rejects_duplicate_tool_names() -> None:
    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(CurrentTimeTool())


@pytest.mark.asyncio
async def test_current_time_tool_returns_structured_data() -> None:
    result = await ToolExecutor(_registry_with(CurrentTimeTool())).execute("get_current_time")
    assert result.success is True
    assert result.data is not None
    assert result.data["datetime"]
    assert result.data["date"]
    assert result.data["time"]


@pytest.mark.asyncio
async def test_system_status_tool_returns_resource_data() -> None:
    result = await ToolExecutor(_registry_with(SystemStatusTool())).execute("get_system_status")
    assert result.success is True
    assert result.data is not None
    assert result.data["hostname"]
    assert 0 <= result.data["cpu_percent"] <= 100
    assert "percent" in result.data["memory"]
    assert "percent" in result.data["disk"]


@pytest.mark.asyncio
async def test_executor_denies_write_tools() -> None:
    result = await ToolExecutor(_registry_with(DummyWriteTool())).execute("dummy_write")
    assert result.success is False
    assert result.error == "Tool execution is not permitted at this safety level."


def _registry_with(tool: JarvisTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(tool)
    return registry
