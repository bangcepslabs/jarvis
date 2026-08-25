"""Compare Router payload/message variants using sanitized provider metadata."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.agent.models import ChatMessage
from app.core.config import get_settings
from app.llm.exceptions import LLMProviderError, LLMRateLimitError


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


def schema(names: list[str], nullable: bool) -> dict[str, object]:
    enum: list[object] = ["NONE", *names]
    prop: dict[str, object] = {"enum": [*enum, None]} if nullable else {"type": "string", "enum": enum}
    if nullable:
        prop["type"] = ["string", "null"]
    return {"type": "json_schema", "json_schema": {"name": "tool_route_decision", "strict": True, "schema": {"type": "object", "properties": {"tool_name": prop}, "required": ["tool_name"], "additionalProperties": False}}}


async def main() -> None:
    settings = get_settings()
    service = get_chat_service()
    agent = service._agent
    provider = agent._llm_provider
    names = [item["function"]["name"] for item in agent._tool_registry.get_llm_tools()]
    hints = "\n".join(f"{item['name']}: {item['routing_hint']}" for item in agent._tool_registry.get_routing_hints())
    base = "Choose exactly one capability or NONE.\nAvailable capabilities:\n" + hints
    context = [
        ChatMessage(role="system", content=base),
        ChatMessage(role="user", content="오늘 부산 날씨 어때?"),
        ChatMessage(role="assistant", content="부산 현재 날씨를 확인했습니다."),
        ChatMessage(role="user", content="그럼 내일은?"),
    ]
    cases = [
        ("A_current_nullable", context, schema(names, True), None),
        ("B_strict", context, schema(names, False), None),
        ("C_strict_hidden", context, schema(names, False), "hidden"),
        ("D_single_classification_hidden", [ChatMessage(role="system", content=base + "\nRecent context: User asked about current weather in Busan; assistant answered with current weather information.\nCurrent request: 그럼 내일은?\nReturn only the structured routing decision.")], schema(names, False), "hidden"),
    ]
    emit({"configuration": {"model": settings.llm_router_model or settings.llm_model, "reasoning_effort": settings.llm_router_reasoning_effort or settings.llm_reasoning_effort, "max_completion_tokens": settings.llm_router_max_completion_tokens}})
    for label, messages, response_format, reasoning_format in cases:
        try:
            response = await provider.chat(messages, response_format=response_format, model=settings.llm_router_model or settings.llm_model, temperature=settings.llm_router_temperature, max_completion_tokens=settings.llm_router_max_completion_tokens, reasoning_effort=settings.llm_router_reasoning_effort or settings.llm_reasoning_effort, reasoning_format=reasoning_format)
            usage = response.usage
            limit = response.rate_limit
            emit({"case": label, "http": 200, "tool_name": response.content, "prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None), "remaining_tokens": getattr(limit, "remaining_tokens", None), "reset_tokens": getattr(limit, "reset_tokens", None)})
            if limit and limit.remaining_tokens is not None and limit.remaining_tokens < 1500:
                emit({"stopped": "remaining_tokens_low"})
                break
        except LLMRateLimitError as exc:
            info = exc.rate_limit
            emit({"case": label, "http": 429, "retry_after": getattr(info, "retry_after", None), "remaining_tokens": getattr(info, "remaining_tokens", None), "reset_tokens": getattr(info, "reset_tokens", None)})
            break
        except LLMProviderError:
            emit({"case": label, "http": 400, "sanitized_error": getattr(provider, "last_error_metadata", {})})


if __name__ == "__main__":
    asyncio.run(main())
