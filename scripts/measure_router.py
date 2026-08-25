"""Run a real, selection-only Router smoke test without executing tools."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.core.config import get_settings

CASES = (
    ("오늘 진짜 피곤하다.", None),
    ("지금 몇 시야?", "get_current_time"),
    ("오늘 부산 날씨 어때?", "get_current_weather"),
    ("내일 부산 비 와?", "get_weather_forecast"),
    ("현재 CPU 상태 알려줘.", "get_system_status"),
)


def emit(data: dict[str, object]) -> None:
    print(json.dumps(data, ensure_ascii=False), flush=True)


async def main() -> None:
    settings = get_settings()
    service = get_chat_service()
    agent = service._agent
    registry = agent._tool_registry
    tools = registry.get_llm_tools()
    hints = registry.get_routing_hints()
    emit({
        "preflight": {
            "model": settings.llm_router_model or settings.llm_model,
            "temperature": settings.llm_router_temperature,
            "reasoning_effort": settings.llm_router_reasoning_effort or settings.llm_reasoning_effort,
            "max_completion_tokens": settings.llm_router_max_completion_tokens,
            "tool_count": len(tools),
            "tool_names": [item["function"]["name"] for item in tools],
            "routing_hint_chars": len(json.dumps(hints, ensure_ascii=False)),
            "all_tool_schema_chars": len(json.dumps(tools, ensure_ascii=False)),
        }
    })
    if len(tools) != 8:
        emit({"error": "Router test aborted", "expected": 8, "actual": len(tools)})
        return
    for message, expected in CASES:
        decision = await agent._tool_router.route(message)
        usage = agent._tool_router.last_usage
        limit = agent._tool_router.last_rate_limit
        emit({
            "input": message,
            "expected": expected,
            "actual": decision.tool_name,
            "pass": decision.tool_name == expected,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "finish_reason": agent._tool_router.last_finish_reason,
            "remaining_tokens": getattr(limit, "remaining_tokens", None),
            "reset_tokens": getattr(limit, "reset_tokens", None),
            "retry_after": getattr(limit, "retry_after", None),
            "error": agent._tool_router.last_error,
        })
        if limit and limit.remaining_tokens is not None and limit.remaining_tokens < 1500:
            emit({"stopped": "remaining_tokens_low", "remaining_tokens": limit.remaining_tokens})
            break


if __name__ == "__main__":
    asyncio.run(main())
