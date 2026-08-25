import asyncio

from app.services.docker_exceptions import ContainerNotFoundError, DockerServiceError
from app.services.docker_service import DockerService
from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.docker.models import ContainerArguments, ContainerLogsArguments, ListContainersArguments
from app.tools.models import ToolResult


class ListContainersTool(JarvisTool):
    name = "list_containers"
    routing_hint = "List Docker containers."
    description = """List Docker containers, including stopped containers, with name, image, and state.

Use when the user asks what containers exist or are running.
Do NOT use for detailed status or logs of one named container."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = ListContainersArguments

    def __init__(self, service: DockerService) -> None:
        self._service = service

    async def execute(self, arguments: ListContainersArguments) -> ToolResult:
        try:
            data = await asyncio.to_thread(self._service.list_containers, arguments.all)
            return ToolResult(success=True, tool_name=self.name, data=data)
        except DockerServiceError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))


class GetContainerStatusTool(JarvisTool):
    name = "get_container_status"
    routing_hint = "Status of one named Docker container."
    description = """Get status and details for one specific Docker container.

Use when the user asks whether a named container is running or requests its status.
Do NOT use for host CPU/memory status or container logs."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = ContainerArguments

    def __init__(self, service: DockerService) -> None:
        self._service = service

    async def execute(self, arguments: ContainerArguments) -> ToolResult:
        try:
            data = await asyncio.to_thread(self._service.get_container_status, arguments.container)
            return ToolResult(success=True, tool_name=self.name, data=data)
        except ContainerNotFoundError:
            return ToolResult(success=False, tool_name=self.name, error="Container not found.")
        except DockerServiceError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))


class GetContainerLogsTool(JarvisTool):
    name = "get_container_logs"
    routing_hint = "Logs of one named Docker container."
    description = """Read recent logs or output from one specific Docker container.

Use only when the user requests logs, output, or errors from a container.
Do NOT use for a simple running/stopped status request."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = ContainerLogsArguments

    def __init__(self, service: DockerService) -> None:
        self._service = service

    async def execute(self, arguments: ContainerLogsArguments) -> ToolResult:
        try:
            data = await asyncio.to_thread(self._service.get_container_logs, arguments.container, arguments.tail)
            return ToolResult(success=True, tool_name=self.name, data=data)
        except ContainerNotFoundError:
            return ToolResult(success=False, tool_name=self.name, error="Container not found.")
        except DockerServiceError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))
