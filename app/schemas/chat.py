from typing import Literal

from pydantic import BaseModel, Field

from app.agent.models import ToolCallSummary
from app.actions.models import PendingActionSummary


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: str = Field(default="default", min_length=1, max_length=100)
    response_mode: Literal["voice", "text"] | None = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    pending_action: PendingActionSummary | None = None
