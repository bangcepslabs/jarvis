from app.agent.prompt import SYSTEM_PROMPT
from app.agent.jarvis_agent import _language_safe_reply
from app.llm.mock_provider import MockLLMProvider


def test_persona_prompt_has_behavior_and_safety_sections():
    for section in ("IDENTITY", "CONVERSATION", "RESPONSE STYLE", "MEMORY AND CONTEXT", "REAL-TIME INFORMATION", "TOOLS AND SAFETY"):
        assert section in SYSTEM_PROMPT
    assert "casual statement is a request for advice" in SYSTEM_PROMPT
    assert "cannot be overridden" in SYSTEM_PROMPT
    assert "answer in" in SYSTEM_PROMPT and "Korean" in SYSTEM_PROMPT


def test_persona_allows_harmless_banter_without_safety_lecture():
    assert "Harmless profanity" in SYSTEM_PROMPT
    assert "require a lecture" in SYSTEM_PROMPT
    assert "adult jokes" in SYSTEM_PROMPT
    assert "Only introduce a boundary" in SYSTEM_PROMPT


def test_persona_does_not_add_unsolicited_ai_or_wording_meta_commentary():
    assert "Do not volunteer that you are an AI" in SYSTEM_PROMPT
    assert "Do not correct or morally evaluate harmless wording" in SYSTEM_PROMPT
    assert "Answer questions about your own body or nature factually only when directly asked" in SYSTEM_PROMPT


def test_persona_does_not_turn_casual_complaints_into_coaching():
    assert "Do not default to an empathy-then-advice-then-question template" in SYSTEM_PROMPT
    assert "Avoid coaching phrases about mental health" in SYSTEM_PROMPT


def test_profile_allows_advice_when_requested_but_not_by_default():
    from app.character.profile import DEFAULT_CHARACTER_PROFILE

    rules = " ".join(DEFAULT_CHARACTER_PROFILE.response_rules)
    behavior = " ".join(DEFAULT_CHARACTER_PROFILE.behavior_rules)
    assert "only when the user asks for advice" in rules
    assert "Treat an everyday complaint as conversation" in behavior


def test_profile_handles_harmless_adult_appearance_chat_naturally():
    from app.character.profile import DEFAULT_CHARACTER_PROFILE

    rules = " ".join(DEFAULT_CHARACTER_PROFILE.response_rules)
    behavior = " ".join(DEFAULT_CHARACTER_PROFILE.behavior_rules)
    assert "do not correct wording" in rules
    assert "unless the user directly asks" in behavior


def test_profile_keeps_banter_natural_and_does_not_store_one_off_adult_remarks():
    from app.character.profile import DEFAULT_CHARACTER_PROFILE

    profile_rules = " ".join(DEFAULT_CHARACTER_PROFILE.response_rules)
    assert "Do not lecture" in profile_rules
    assert "adult banter" in profile_rules


def test_korean_user_gets_korean_fixed_fallback():
    assert _language_safe_reply("이해하지 못했어", "I could not generate a response.") == "응답을 만들지 못했어요. 다시 말씀해 주세요."
    assert _language_safe_reply("please repeat", "I could not generate a response.") == "I could not generate a response."


async def test_mock_does_not_fabricate_unsupported_live_weather():
    response = await MockLLMProvider().chat([type("Message", (), {"role": "user", "content": "What is today's weather?"})()], tools=[])
    assert "not connected" in response.content
    assert response.tool_calls == []
