"""Measure the production 3-turn weather pipeline without logging raw secrets."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.core.config import get_settings
from app.llm.exceptions import LLMRateLimitError

QUERIES = (
    "오늘 부산 날씨 어때?",
    "그럼 내일은?",
    "아 비 오면 귀찮은데.",
)
CONVERSATION_ID = "post4-full-pipeline-weather"


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


async def main() -> None:
    settings = get_settings()
    service = get_chat_service()
    agent = service._agent
    provider = agent._llm_provider
    registry = agent._tool_registry
    all_schema = registry.get_llm_tools()
    hints = registry.get_routing_hints()
    records: list[dict[str, object]] = []
    original_chat = provider.chat

    async def captured_chat(messages, tools=None, tool_choice=None, **kwargs):
        if kwargs.get("response_format"):
            phase = "router"
        elif tools and isinstance(tool_choice, dict):
            phase = "argument_generation"
        elif tools == []:
            phase = "conversation_response" if tool_choice == "none" else "main"
        else:
            phase = "main"
        try:
            response = await original_chat(messages, tools=tools, tool_choice=tool_choice, **kwargs)
        except LLMRateLimitError as exc:
            info = exc.rate_limit
            records.append({"phase": phase, "429": True, "retry_after": getattr(info, "retry_after", None), "remaining_requests": getattr(info, "remaining_requests", None), "remaining_tokens": getattr(info, "remaining_tokens", None), "reset_tokens": getattr(info, "reset_tokens", None)})
            raise
        usage = response.usage
        limit = response.rate_limit
        record = {
            "phase": phase,
            "model": kwargs.get("model") or settings.llm_model,
            "tool_name": response.tool_calls[0].name if response.tool_calls else None,
            "arguments": response.tool_calls[0].arguments if response.tool_calls else None,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "finish_reason": response.finish_reason,
            "remaining_requests": getattr(limit, "remaining_requests", None),
            "remaining_tokens": getattr(limit, "remaining_tokens", None),
            "reset_tokens": getattr(limit, "reset_tokens", None),
            "retry_after": getattr(limit, "retry_after", None),
            "prompt_chars": sum(len(item.content) for item in messages),
            "conversation_chars": sum(len(item.content) for item in messages if item.role in ("user", "assistant")),
            "tool_schema_chars": len(json.dumps(tools or [], ensure_ascii=False)),
        }
        records.append(record)
        return response

    provider.chat = captured_chat
    emit({"configuration": {"main_model": settings.llm_model, "main_reasoning_effort": settings.llm_reasoning_effort, "main_temperature": settings.llm_temperature, "router_model": settings.llm_router_model or settings.llm_model, "router_reasoning_effort": settings.llm_router_reasoning_effort or settings.llm_reasoning_effort, "router_temperature": settings.llm_router_temperature, "router_max_completion_tokens": settings.llm_router_max_completion_tokens}})
    emit({"schema": {"routing_hint_chars": len(json.dumps(hints, ensure_ascii=False)), "all_tool_schema_chars": len(json.dumps(all_schema, ensure_ascii=False)), "tool_count": len(all_schema)}})

    offset = 0
    for turn, query in enumerate(QUERIES, 1):
        before = len(records)
        try:
            response = await service.chat(query, CONVERSATION_ID)
            turn_records = records[before:]
            totals = {key: sum((item.get(key) or 0) for item in turn_records if isinstance(item.get(key), int)) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
            emit({"turn": turn, "input": query, "reply": response.reply, "tool_calls": [item.model_dump() for item in response.tool_calls], "calls": turn_records, "turn_totals": totals})
            if any(item.get("429") for item in turn_records):
                emit({"stopped": "429"})
                break
            if any(isinstance(item.get("remaining_tokens"), int) and item["remaining_tokens"] < 1500 for item in turn_records):
                emit({"stopped": "remaining_tokens_low"})
                break
        except Exception as exc:
            emit({"turn": turn, "error_type": type(exc).__name__, "error": str(exc), "calls": records[before:]})
            break


if __name__ == "__main__":
    asyncio.run(main())
