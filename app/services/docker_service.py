from typing import Any

import docker
from docker.errors import DockerException, NotFound

from app.services.docker_exceptions import ContainerNotFoundError, DockerUnavailableError


class DockerService:
    """Small Docker SDK boundary used by read-only tools."""

    def __init__(self, client: Any | None = None, timeout: float = 5.0) -> None:
        self._client = client
        self._timeout = timeout

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                self._client = docker.from_env(timeout=self._timeout)
            except DockerException as exc:
                raise DockerUnavailableError("Docker Engine is unavailable.") from exc
        return self._client

    def list_containers(self, all: bool = True) -> dict[str, Any]:
        try:
            containers = self.client.containers.list(all=all)
            items = [self._summary(container) for container in containers]
        except DockerException as exc:
            raise DockerUnavailableError("Docker Engine is unavailable.") from exc
        running = sum(item["state"] == "running" for item in items)
        return {"containers": items, "total": len(items), "running": running, "stopped": len(items) - running}

    def get_container_status(self, container: str) -> dict[str, Any]:
        try:
            item = self.client.containers.get(container)
            state = (getattr(item, "attrs", {}) or {}).get("State", {}) or {}
            summary = self._summary(item)
            summary.update(
                {
                    "running": bool(state.get("Running", summary["state"] == "running")),
                    "started_at": state.get("StartedAt"),
                    "finished_at": state.get("FinishedAt"),
                    "restart_count": (getattr(item, "attrs", {}) or {}).get("RestartCount", 0),
                }
            )
            return summary
        except NotFound as exc:
            raise ContainerNotFoundError("Container not found.") from exc
        except DockerException as exc:
            raise DockerUnavailableError("Docker Engine is unavailable.") from exc

    def get_container_logs(self, container: str, tail: int = 100, max_chars: int = 20000) -> dict[str, Any]:
        try:
            item = self.client.containers.get(container)
            raw_logs = item.logs(tail=tail)
        except NotFound as exc:
            raise ContainerNotFoundError("Container not found.") from exc
        except DockerException as exc:
            raise DockerUnavailableError("Docker Engine is unavailable.") from exc
        logs = raw_logs.decode("utf-8", errors="replace") if isinstance(raw_logs, bytes) else str(raw_logs)
        truncated = len(logs) > max_chars
        if truncated:
            logs = logs[-max_chars:]
        return {"container": container, "tail": tail, "logs": logs, "truncated": truncated}

    def restart_container(self, container: str, timeout: int = 10) -> dict[str, Any]:
        try:
            item = self.client.containers.get(container)
            item.restart(timeout=timeout)
            status = getattr(item, "status", "unknown")
            try:
                item.reload()
                status = getattr(item, "status", status)
            except DockerException:
                pass
            return {"container": container, "status": status, "restarted": True}
        except NotFound as exc:
            raise ContainerNotFoundError("Container not found.") from exc
        except DockerException as exc:
            raise DockerUnavailableError("Docker Engine is unavailable.") from exc

    @staticmethod
    def _summary(container: Any) -> dict[str, Any]:
        name = str(getattr(container, "name", "")).lstrip("/")
        image = getattr(container, "image", None)
        tags = getattr(image, "tags", None) or []
        image_name = tags[0] if tags else str(getattr(image, "short_id", "unknown"))
        status = str(getattr(container, "status", "unknown"))
        return {"id": str(getattr(container, "short_id", getattr(container, "id", ""))), "name": name, "image": image_name, "status": status, "state": status}
