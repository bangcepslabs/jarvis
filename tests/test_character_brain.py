import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.agent.models import ChatMessage
from app.character.context import build_character_context
from app.character.profile import CharacterProfile, DEFAULT_AVATAR_IDENTITY, DEFAULT_CHARACTER_PROFILE
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


def test_default_profile_discourages_counselor_tone():
    context = build_character_context(DEFAULT_CHARACTER_PROFILE)
    assert "counselor or customer-service tone" in context
    assert "Do not lead with obligatory sympathy" in context
    assert "do not turn an ordinary chat into life coaching" in context
    assert "do not summarize, analyze, or list the user's memories as a profile" in context
    assert "Do not combine separate facts" in context


def test_character_context_keeps_adult_banter_non_explicit_and_in_character():
    context = build_character_context(DEFAULT_CHARACTER_PROFILE)

    assert "suggestive banter" in context
    assert "playful implication" in context
    assert "fade-to-black" in context
    assert "policy explanation" in context
    assert "customer-service closings" in context


def test_character_context_contains_active_avatar_self_identity():
    context = build_character_context(DEFAULT_CHARACTER_PROFILE, avatar_identity=DEFAULT_AVATAR_IDENTITY, current_expression="happy", current_motion="idle2")
    assert "AVATAR SELF-IDENTITY" in context
    assert "avatar_name=Ellen" in context
    assert "model=ellen_dev" in context
    assert "current_expression=happy" in context
    assert "current_motion=idle2" in context
    assert "Do not claim it is a physical human body" in context


def test_avatar_identity_does_not_invent_unverified_appearance():
    context = build_character_context(DEFAULT_CHARACTER_PROFILE, avatar_identity=DEFAULT_AVATAR_IDENTITY)
    assert "only profile-verified appearance details should be discussed" in context


def test_character_brain_tracks_state_per_conversation():
    brain = CharacterBrain()
    response = type("Response", (), {"tool_calls": [], "pending_action": None})()
    brain.observe("a", "hello", response)
    assert "hello" in brain.context("a")
    assert "unknown" in brain.context("b")


def test_runtime_state_plans_teasing_reaction_without_authorization_effects():
    brain = CharacterBrain()
    brain.prepare("a", "너 오늘 좀 예쁜데 ㅋㅋ")

    context = brain.context("a")
    assert "recent_dynamic=teasing" in context
    assert "emotion=embarrassed" in context
    assert "speaking_style=short_deflecting" in context
    assert "never authorization" in context


def test_runtime_state_continues_teasing_and_decays_transient_emotion():
    brain = CharacterBrain()
    brain.prepare("a", "너 방금 좀 야했는데?")
    first = brain.context("a")
    brain.prepare("a", "뭐야 갑자기 부끄러워? ㅋㅋ")
    second = brain.context("a")

    assert "emotion=embarrassed" in first
    assert "emotion=playful" in second
    assert "recent_dynamic=teasing" in second

    brain.prepare("a", "오늘 서버 CPU 몇이야?")
    technical = brain.context("a")
    assert "recent_dynamic=technical" in technical
    assert "emotion=focused" in technical


def test_runtime_reaction_maps_to_existing_presentation_contract():
    brain = CharacterBrain()
    brain.prepare("a", "너 방금 좀 야했는데?")

    hint = brain.presentation_hint("a")

    assert hint.emotion == "playful"
    assert hint.motion_intent == "reaction"
    assert hint.reaction == "acknowledge"


@pytest.mark.asyncio
async def test_agent_includes_character_context_without_memory():
    provider = ContextProvider()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()))
    await agent.respond("hello")
    system = provider.messages[0].content
    assert "CHARACTER BRAIN CONTEXT" in system
    assert "JARVIS" in system
