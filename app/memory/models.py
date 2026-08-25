from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryCategory(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    PROJECT = "project"
    ENVIRONMENT = "environment"
    OTHER = "other"
    ROUTINE = "routine"
    COMMUNICATION_STYLE = "communication_style"


class MemorySource(StrEnum):
    EXPLICIT = "explicit"
    ADAPTIVE = "adaptive"


class MemoryEntry(BaseModel):
    id: int | None = None
    category: MemoryCategory
    key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime
    updated_at: datetime
    source: MemorySource = MemorySource.EXPLICIT


class MemoryAction(StrEnum):
    SAVE = "SAVE"
    UPDATE = "UPDATE"
    IGNORE = "IGNORE"


class MemoryDecision(BaseModel):
    action: MemoryAction
    category: MemoryCategory | None = None
    key: str | None = None
    value: str | None = None
    reason: str | None = None
