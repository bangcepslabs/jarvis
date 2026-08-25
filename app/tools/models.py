from typing import Any

from pydantic import BaseModel, ConfigDict


class EmptyToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolMetadata(BaseModel):
    name: str
    description: str
    safety_level: str
    parameters: dict[str, Any]


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    data: dict[str, Any] | None = None
    error: str | None = None
