import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.agent.prompt import build_system_prompt
from app.agent.presentation import parse_presentation_response
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class SequencedProvider(LLMProvider):
    def __init__(self, replies: list[str]) -> None:
        self._replies = iter(replies)
        self.requests = []

    async def chat(self, messages, tools=None, tool_choice=None, **kwargs):
        self.requests.append(messages)
        return LLMResponse(content=next(self._replies), finish_reason="stop")


def test_main_prompt_requires_visible_reply_and_delegates_ordinary_hint_to_character_brain():
    prompt = build_system_prompt()

    assert "MUST first return a non-empty, natural-language reply" in prompt
    assert "Character Brain generates ordinary presentation metadata separately" in prompt
    assert "do not emit JARVIS_PRESENTATION metadata for ordinary replies" in prompt


@pytest.mark.asyncio
async def test_marker_only_response_retries_text_only_and_uses_character_brain_hint():
    marker = '<!--JARVIS_PRESENTATION {"emotion":"happy","intensity":1.0}-->'
    provider = SequencedProvider([marker, "plain visible reply"])
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()))

    response = await agent.respond("hello")

    assert response.reply == "plain visible reply"
    assert response.response_origin == "llm_retry"
    assert response.presentation_hint is not None
    assert response.presentation_hint.emotion == "neutral"
    retry_instruction = provider.requests[1][1].content
    assert "Do not emit JARVIS_PRESENTATION metadata" in retry_instruction


def test_legacy_reply_and_marker_parser_remains_supported():
    reply, hint = parse_presentation_response(
        'visible reply <!--JARVIS_PRESENTATION {"emotion":"happy","intensity":0.7}-->'
    )

    assert reply == "visible reply"
    assert hint.emotion == "happy"
    assert hint.intensity == 0.7
