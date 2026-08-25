"""Validate Web/News Router selection with four independent requests."""

import asyncio
import json

from app.api.dependencies import get_chat_service
from app.core.config import get_settings

CASES = (
    ("오늘 AI 뉴스 뭐 있어?", "search_news"),
    ("FastAPI 최신 버전 변경점 찾아줘", "web_search"),
    ("오늘 부산 날씨 어때?", "get_current_weather"),
    ("오늘 아무것도 하기 싫다.", None),
)


async def main() -> None:
    settings = get_settings()
    agent = get_chat_service()._agent
    tools = agent._tool_registry.get_llm_tools()
    print(json.dumps({"preflight": {"application": settings.app_name, "version": settings.app_version, "main_model": settings.llm_model, "router_model": settings.llm_router_model or settings.llm_model, "search_provider": settings.search_provider, "web_search_enabled": settings.web_search_enabled, "tavily_key_configured": bool(settings.tavily_api_key), "tool_count": len(tools), "tool_names": [item["function"]["name"] for item in tools]}}, ensure_ascii=False), flush=True)
    passed = 0
    for query, expected in CASES:
        decision = await agent._tool_router.route(query)
        usage = agent._tool_router.last_usage
        limit = agent._tool_router.last_rate_limit
        ok = decision.tool_name == expected
        passed += int(ok)
        print(json.dumps({"input": query, "expected": expected or "NONE", "actual": decision.tool_name or "NONE", "pass": ok, "prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None), "remaining_requests": getattr(limit, "remaining_requests", None), "remaining_tokens": getattr(limit, "remaining_tokens", None), "reset_tokens": getattr(limit, "reset_tokens", None), "retry_after": getattr(limit, "retry_after", None)}, ensure_ascii=False), flush=True)
        if limit and limit.remaining_tokens is not None and limit.remaining_tokens < 1500:
            print(json.dumps({"stopped": "remaining_tokens_low"}), flush=True)
            break
    print(json.dumps({"accuracy": f"{passed}/{len(CASES)}"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
