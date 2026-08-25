from datetime import datetime

from pydantic import BaseModel

from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.models import ToolResult


class CurrentTimeTool(JarvisTool):
    name = "get_current_time"
    routing_hint = "Current clock time, date, day, or timezone only."
    description = """Get the current date and clock time.

Use ONLY for current time, date, day, or timezone questions.
Do NOT use for weather, forecasts, CPU/system status, or Docker status, even if the request says today, tomorrow, or current."""
    safety_level = ToolSafetyLevel.READ_ONLY

    async def execute(self, arguments: BaseModel) -> ToolResult:
        now = datetime.now().astimezone()
        return ToolResult(
            success=True,
            tool_name=self.name,
            data={
                "datetime": now.isoformat(),
                "date": now.date().isoformat(),
                "time": now.time().replace(microsecond=0).isoformat(),
                "timezone": str(now.tzinfo),
            },
        )
