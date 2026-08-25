"""Optional single-request Groq/Qwen smoke test.

This is intentionally separate from pytest and never prints the API key or
model response. Run with LLM_PROVIDER=openai, a Groq base URL, and LLM_API_KEY
configured in the environment.
"""
import asyncio

from app.agent.models import ChatMessage
from app.core.config import get_settings
from app.llm.provider import create_llm_provider


async def main() -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        print("Groq smoke test skipped: LLM_API_KEY is not configured.")
        return
    provider = create_llm_provider(settings)
    response = await provider.chat([ChatMessage(role="user", content="Reply with one short greeting.")])
    usage = response.usage
    limits = response.rate_limit
    print("Groq smoke test succeeded")
    print(f"tool_calls={len(response.tool_calls)}")
    print(f"prompt_tokens={getattr(usage, 'prompt_tokens', None)} completion_tokens={getattr(usage, 'completion_tokens', None)} total_tokens={getattr(usage, 'total_tokens', None)}")
    print(f"remaining_requests={getattr(limits, 'remaining_requests', None)} remaining_tokens={getattr(limits, 'remaining_tokens', None)} retry_after={getattr(limits, 'retry_after', None)}")


if __name__ == "__main__":
    asyncio.run(main())
