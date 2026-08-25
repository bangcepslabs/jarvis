"""Run one real News full pipeline turn with metadata-only reporting."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.llm.exceptions import LLMRateLimitError


async def main() -> None:
    service = get_chat_service()
    agent = service._agent
    settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings()
    provider = agent._llm_provider
    records = []
    original_chat = provider.chat
    original_execute = agent._tool_executor.execute

    async def captured_chat(messages, tools=None, tool_choice=None, **kwargs):
        phase = "router" if kwargs.get("response_format") else ("argument_generation" if tools and isinstance(tool_choice, dict) else "synthesis")
        response = await original_chat(messages, tools=tools, tool_choice=tool_choice, **kwargs)
        usage = response.usage
        limit = response.rate_limit
        records.append({"phase": phase, "model": kwargs.get("model") or settings.llm_model, "tool_name": response.tool_calls[0].name if response.tool_calls else None, "arguments": response.tool_calls[0].arguments if response.tool_calls else None, "prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None), "finish_reason": response.finish_reason, "remaining_tokens": getattr(limit, "remaining_tokens", None), "reset_tokens": getattr(limit, "reset_tokens", None), "retry_after": getattr(limit, "retry_after", None), "tool_schema_chars": len(json.dumps(tools or [], ensure_ascii=False))})
        return response

    async def captured_execute(tool_name, arguments=None, authorization=None):
        result = await original_execute(tool_name, arguments, authorization)
        data = result.data or {}
        print(json.dumps({"tool": tool_name, "safety": getattr(agent._tool_registry.get(tool_name), "safety_level", None), "success": result.success, "provider": data.get("topic", "tavily"), "result_count": len(data.get("results", [])) if isinstance(data.get("results"), list) else None, "source_preserved": bool(data.get("results") and data["results"][0].get("source")), "url_preserved": bool(data.get("results") and data["results"][0].get("url")), "published_at_field_present": bool(data.get("results") and "published_at" in data["results"][0]), "retrieved_at_field_present": bool(data.get("results") and "retrieved_at" in data["results"][0])}, ensure_ascii=False), flush=True)
        return result

    provider.chat = captured_chat
    agent._tool_executor.execute = captured_execute
    try:
        response = await service.chat("오늘 AI 뉴스 뭐 있어?", "v048-real-news")
        totals = {key: sum((item.get(key) or 0) for item in records) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        print(json.dumps({"configuration": {"main_model": settings.llm_model, "router_model": settings.llm_router_model, "search_provider": settings.search_provider}, "reply_present": bool(response.reply), "tool_calls": [item.model_dump() for item in response.tool_calls], "calls": records, "turn_totals": totals}, ensure_ascii=False, default=str), flush=True)
    except LLMRateLimitError as exc:
        info = exc.rate_limit
        print(json.dumps({"429": True, "remaining_tokens": getattr(info, "remaining_tokens", None), "reset_tokens": getattr(info, "reset_tokens", None), "retry_after": getattr(info, "retry_after", None)}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
