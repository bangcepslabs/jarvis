import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class MarkerThenReplyProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, tools=None, tool_choice=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content='<!--JARVIS_PRESENTATION {"emotion":"neutral"}-->'
            )
        return LLMResponse(content="이번엔 제대로 답할게.")


@pytest.mark.asyncio
async def test_marker_only_main_response_is_retried_before_fallback():
    provider = MarkerThenReplyProvider()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()))

    response = await agent.respond("오늘 뭐 해?")

    assert provider.calls == 2
    assert response.reply == "이번엔 제대로 답할게."
