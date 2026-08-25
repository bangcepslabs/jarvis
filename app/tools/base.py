from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.tools.models import EmptyToolArguments, ToolMetadata, ToolResult


class ToolSafetyLevel(StrEnum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DANGEROUS = "dangerous"


class JarvisTool(ABC):
    name: str
    description: str
    routing_hint: str = ""
    safety_level: ToolSafetyLevel = ToolSafetyLevel.READ_ONLY
    arguments_model: type[BaseModel] = EmptyToolArguments

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            safety_level=self.safety_level,
            parameters=self.arguments_model.model_json_schema(),
        )

    @abstractmethod
    async def execute(self, arguments: BaseModel) -> ToolResult:
        """Execute a validated tool operation."""
