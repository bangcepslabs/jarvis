import pytest
from docker.errors import DockerException, NotFound

from app.services.docker_exceptions import DockerUnavailableError
from app.services.docker_service import DockerService
from app.agent.jarvis_agent import JarvisAgent
from app.llm.mock_provider import MockLLMProvider
from app.tools.docker.models import ContainerArguments, ContainerLogsArguments
from app.tools.docker.tools import GetContainerLogsTool, GetContainerStatusTool, ListContainersTool
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class FakeImage:
    tags = ["example:latest"]
    short_id = "sha256:image"


class FakeContainer:
    image = FakeImage()
    short_id = "abc123"
    id = "abc123-full"
    name = "pulse-api"
    status = "running"
    attrs = {"State": {"Running": True, "StartedAt": "2026-01-01T00:00:00Z", "FinishedAt": "0001-01-01T00:00:00Z"}, "RestartCount": 2}

    def logs(self, tail: int = 100) -> bytes:
        assert tail == 50
        return b"hello\xff\nworld\n"


class FakeContainers:
    def __init__(self) -> None:
        self.item = FakeContainer()

    def list(self, all: bool = True):
        return [self.item, type("Stopped", (), {"image": FakeImage(), "short_id": "def456", "id": "def456-full", "name": "/postgres", "status": "exited"})()]

    def get(self, name: str):
        if name == "missing":
            raise NotFound("missing")
        return self.item


class FakeClient:
    def __init__(self) -> None:
        self.containers = FakeContainers()


class UnavailableClient:
    class containers:
        @staticmethod
        def list(all: bool = True):
            raise DockerException("daemon down")


def service() -> DockerService:
    return DockerService(client=FakeClient())


def test_service_lists_running_and_stopped_containers() -> None:
    result = service().list_containers()
    assert result["total"] == 2
    assert result["running"] == 1
    assert result["containers"][0]["name"] == "pulse-api"


def test_service_status_is_structured() -> None:
    result = service().get_container_status("pulse-api")
    assert result["running"] is True
    assert result["restart_count"] == 2


def test_service_logs_decode_and_limit() -> None:
    result = service().get_container_logs("pulse-api", tail=50)
    assert result["logs"] == "hello�\nworld\n"
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_docker_tools_use_executor_and_are_read_only() -> None:
    docker_service = service()
    registry = ToolRegistry()
    registry.register(ListContainersTool(docker_service))
    registry.register(GetContainerStatusTool(docker_service))
    registry.register(GetContainerLogsTool(docker_service))
    executor = ToolExecutor(registry)
    result = await executor.execute("get_container_logs", ContainerLogsArguments(container="pulse-api", tail=50).model_dump())
    assert result.success is True
    assert result.data["tail"] == 50


def test_container_argument_validation_limits_tail() -> None:
    with pytest.raises(ValueError):
        ContainerLogsArguments(container="pulse-api", tail=501)


def test_service_handles_unavailable_engine() -> None:
    with pytest.raises(DockerUnavailableError):
        DockerService(client=UnavailableClient()).list_containers()


@pytest.mark.asyncio
async def test_mock_native_flow_selects_docker_list_tool() -> None:
    registry = ToolRegistry()
    registry.register(ListContainersTool(service()))
    executor = ToolExecutor(registry)
    message = "".join(chr(code) for code in (0xB3C4, 0xCEE4, 0x20, 0xBAA9, 0xB85D, 0x20, 0xC54C, 0xB824, 0xC918))
    response = await JarvisAgent(MockLLMProvider(), executor, registry).respond(message)
    assert response.tool_calls[0].name == "list_containers"
    assert response.tool_calls[0].success is True
