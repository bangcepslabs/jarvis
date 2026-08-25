from typing import Any

from pydantic import BaseModel, Field


class LLMToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMRateLimitInfo(BaseModel):
    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    reset_requests: str | None = None
    reset_tokens: str | None = None
    retry_after: str | None = None


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    rate_limit: LLMRateLimitInfo | None = None


class ToolRouteDecision(BaseModel):
    tool_name: str | None = None
