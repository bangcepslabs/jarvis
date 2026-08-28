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


class PresentationHint(BaseModel):
    emotion: Literal["neutral", "happy", "excited", "surprised", "concerned", "thinking", "playful"] = "neutral"
    intensity: float = Field(default=0.3, ge=0.0, le=1.0)
    motion_intent: Literal["none", "subtle", "positive", "reaction"] = "none"
    attitude: Literal["neutral", "friendly", "playful", "supportive", "curious", "serious", "confident"] = "neutral"
    reaction: Literal["none", "acknowledge", "agree", "disagree", "celebrate", "surprise", "worry", "think", "tease", "encourage"] = "none"
    duration: Literal["short", "normal", "hold"] = "normal"


class AgentResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    pending_action: PendingActionSummary | None = None
    presentation_hint: PresentationHint | None = None
