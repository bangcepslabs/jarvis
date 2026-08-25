import logging
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app.actions.models import ActionAuthorization
from app.tools.base import JarvisTool
from app.tools.base import ToolSafetyLevel
from app.tools.models import ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes registered read-only tools after validating their arguments."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def validate_arguments(self, tool_name: str, arguments: dict[str, Any] | None = None) -> tuple[JarvisTool, BaseModel] | ToolResult:
        tool = self._registry.get(tool_name)
        if tool is None:
            return ToolResult(success=False, tool_name=tool_name, error="Requested tool is unavailable.")
        if tool.safety_level == ToolSafetyLevel.DANGEROUS:
            logger.warning("tool_requested name=%s safety=%s denied=true", tool.name, tool.safety_level)
            return ToolResult(success=False, tool_name=tool.name, error="Tool execution is not permitted at this safety level.")
        try:
            validated_arguments = tool.arguments_model.model_validate(arguments or {})
        except ValidationError:
            logger.warning("tool_requested name=%s safety=%s validation_failed=true", tool.name, tool.safety_level)
            return ToolResult(success=False, tool_name=tool.name, error="Tool arguments are invalid.")
        return tool, validated_arguments

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        authorization: ActionAuthorization | None = None,
    ) -> ToolResult:
        validated = self.validate_arguments(tool_name, arguments)
        if isinstance(validated, ToolResult):
            return validated
        tool, validated_arguments = validated
        if tool.safety_level == ToolSafetyLevel.WRITE:
            if authorization is None:
                logger.warning("tool_requested name=%s safety=%s denied=true reason=confirmation_required", tool.name, tool.safety_level)
                return ToolResult(success=False, tool_name=tool.name, error="Tool execution is not permitted at this safety level.")
            if authorization.used or authorization.tool_name != tool.name:
                logger.warning("tool_requested name=%s safety=%s denied=true reason=invalid_authorization", tool.name, tool.safety_level)
                return ToolResult(success=False, tool_name=tool.name, error="Tool authorization is invalid or already used.")
            authorization.used = True

        started_at = perf_counter()
        logger.info("tool_requested name=%s safety=%s", tool.name, tool.safety_level)
        logger.info("tool_started name=%s", tool.name)
        try:
            result = await tool.execute(validated_arguments)
        except Exception:
            logger.exception("tool_failed name=%s", tool.name)
            return ToolResult(success=False, tool_name=tool.name, error="Unable to retrieve the requested information.")

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        if result.success:
            logger.info("tool_completed name=%s duration_ms=%s success=true", tool.name, duration_ms)
        else:
            logger.warning("tool_failed name=%s duration_ms=%s success=false", tool.name, duration_ms)
        return result
