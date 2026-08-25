import platform
import time
from pathlib import Path

import psutil
from pydantic import BaseModel

from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.models import ToolResult


def _gigabytes(value: int | float) -> float:
    return round(value / (1024**3), 2)


class SystemStatusTool(JarvisTool):
    name = "get_system_status"
    routing_hint = "CPU, memory, disk, or local computer health."
    description = """Get local computer resource status such as CPU, memory, disk, and system health.

Use for PC/server resource or health questions.
Do NOT use for date/time, weather, or Docker-specific status."""
    safety_level = ToolSafetyLevel.READ_ONLY

    async def execute(self, arguments: BaseModel) -> ToolResult:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(Path.cwd().anchor)
        uptime_seconds = max(0, int(time.time() - psutil.boot_time()))
        return ToolResult(
            success=True,
            tool_name=self.name,
            data={
                "hostname": platform.node(),
                "os": f"{platform.system()} {platform.release()}",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory": {"percent": memory.percent, "used_gb": _gigabytes(memory.used), "total_gb": _gigabytes(memory.total)},
                "disk": {"percent": disk.percent, "used_gb": _gigabytes(disk.used), "total_gb": _gigabytes(disk.total)},
                "uptime_seconds": uptime_seconds,
            },
        )
