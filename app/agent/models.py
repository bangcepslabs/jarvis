from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.actions.models import PendingActionSummary


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[object] | None = None


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class ToolCallSummary(BaseModel):
    name: str
    success: bool


class AgentResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    pending_action: PendingActionSummary | None = None
