import asyncio

from app.services.docker_exceptions import ContainerNotFoundError, DockerServiceError
from app.services.docker_service import DockerService
from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.docker.models import ContainerArguments
from app.tools.models import ToolResult


class RestartContainerTool(JarvisTool):
    name = "restart_container"
    routing_hint = "Explicitly restart one named Docker container."
    description = """Restart one specific Docker container.

This is a WRITE action. Use only for an explicit restart request; runtime confirmation is required before execution."""
    safety_level = ToolSafetyLevel.WRITE
    arguments_model = ContainerArguments

    def __init__(self, service: DockerService, timeout: int = 10) -> None:
        self._service = service
        self._timeout = timeout

    async def execute(self, arguments: ContainerArguments) -> ToolResult:
        try:
            data = await asyncio.to_thread(self._service.restart_container, arguments.container, self._timeout)
            return ToolResult(success=True, tool_name=self.name, data=data)
        except ContainerNotFoundError:
            return ToolResult(success=False, tool_name=self.name, error="Container not found.")
        except DockerServiceError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))
