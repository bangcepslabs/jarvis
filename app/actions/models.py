from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class PendingAction(BaseModel):
    id: str
    tool_name: str
    arguments: dict[str, Any]
    safety_level: str
    status: ActionStatus
    created_at: datetime
    expires_at: datetime
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    error: str | None = None


class ActionAuthorization(BaseModel):
    action_id: str
    tool_name: str
    approved_at: datetime
    used: bool = False


class PendingActionSummary(BaseModel):
    id: str
    tool_name: str
    status: ActionStatus
