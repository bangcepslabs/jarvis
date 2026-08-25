"""Measure two context-aware Router follow-ups only."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.agent.models import ChatMessage


async def main() -> None:
    agent = get_chat_service()._agent
    cases = [
        ([ChatMessage(role="user", content="\uc624\ub298 \ubd80\uc0b0 \ub0a0\uc528 \uc5b4\ub54c?"), ChatMessage(role="assistant", content="\ubd80\uc0b0 \ud604\uc7ac \ub0a0\uc528\ub97c \ud655\uc778\ud588\uc5b4.")], "\uadf8\ub7fc \ub0b4\uc77c\uc740?", "get_weather_forecast"),
        ([ChatMessage(role="user", content="\uc624\ub298 \ubd80\uc0b0 \ub0a0\uc528 \uc5b4\ub54c?"), ChatMessage(role="assistant", content="\ubd80\uc0b0 \ud604\uc7ac \ub0a0\uc528\ub97c \ud655\uc778\ud588\uc5b4.")], "\ube44 \uc624\uba74 \uadc0\ucc2e\uc740\ub370.", None),
    ]
    for context, query, expected in cases:
        decision = await agent._tool_router.route(query, context)
        usage = agent._tool_router.last_usage
        limit = agent._tool_router.last_rate_limit
        print(json.dumps({"input": query, "expected": expected, "actual": decision.tool_name, "pass": decision.tool_name == expected, "message_count": agent._tool_router.last_context_message_count, "conversation_chars": agent._tool_router.last_context_chars, "prompt_chars": agent._tool_router.last_prompt_chars, "prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None), "remaining_tokens": getattr(limit, "remaining_tokens", None), "reset_tokens": getattr(limit, "reset_tokens", None), "retry_after": getattr(limit, "retry_after", None)}, ensure_ascii=False), flush=True)
        if limit and limit.remaining_tokens is not None and limit.remaining_tokens < 1500:
            break


if __name__ == "__main__":
    asyncio.run(main())
