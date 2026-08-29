import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.agent.models import ChatMessage
from app.character.context import build_character_context
from app.character.profile import CharacterProfile
from app.character.service import CharacterBrain
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class ContextProvider(LLMProvider):
    def __init__(self):
        self.messages: list[ChatMessage] = []

    async def chat(self, messages, tools=None):
        self.messages = messages
        return LLMResponse(content="응답")


def test_character_context_renders_profile_and_continuity_without_authority():
    profile = CharacterProfile("Test", "a helper", ("brief",), ("calm",), behavior_rules=("do not invent facts",))
    context = build_character_context(profile, current_topic="weather", recent_user_intent="forecast", available_tool_names=("weather",))
    assert "Name: Test" in context
    assert "weather" in context
    assert "never authorization" in context


def test_character_brain_tracks_state_per_conversation():
    brain = CharacterBrain()
    response = type("Response", (), {"tool_calls": [], "pending_action": None})()
    brain.observe("a", "hello", response)
    assert "hello" in brain.context("a")
    assert "unknown" in brain.context("b")


@pytest.mark.asyncio
async def test_agent_includes_character_context_without_memory():
    provider = ContextProvider()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()))
    await agent.respond("hello")
    system = provider.messages[0].content
    assert "CHARACTER BRAIN CONTEXT" in system
    assert "JARVIS" in system
