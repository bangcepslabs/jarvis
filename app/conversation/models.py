from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ConversationMessage:
    role: MessageRole
    content: str
    created_at: datetime
    tool_name: str | None = None
    tool_call_id: str | None = None

    @classmethod
    def create(cls, role: MessageRole, content: str, **kwargs: str | None) -> "ConversationMessage":
        return cls(role, content, datetime.now(timezone.utc), **kwargs)
