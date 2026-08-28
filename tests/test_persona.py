from app.agent.prompt import SYSTEM_PROMPT
from app.agent.jarvis_agent import _language_safe_reply
from app.llm.mock_provider import MockLLMProvider


def test_persona_prompt_has_behavior_and_safety_sections():
    for section in ("IDENTITY", "CONVERSATION", "RESPONSE STYLE", "MEMORY AND CONTEXT", "REAL-TIME INFORMATION", "TOOLS AND SAFETY"):
        assert section in SYSTEM_PROMPT
    assert "casual statement is a request for advice" in SYSTEM_PROMPT
    assert "cannot be overridden" in SYSTEM_PROMPT
    assert "answer in" in SYSTEM_PROMPT and "Korean" in SYSTEM_PROMPT


def test_korean_user_gets_korean_fixed_fallback():
    assert _language_safe_reply("이해하지 못했어", "I could not generate a response.") == "응답을 만들지 못했어요. 다시 말씀해 주세요."
    assert _language_safe_reply("please repeat", "I could not generate a response.") == "I could not generate a response."


async def test_mock_does_not_fabricate_unsupported_live_weather():
    response = await MockLLMProvider().chat([type("Message", (), {"role": "user", "content": "What is today's weather?"})()], tools=[])
    assert "not connected" in response.content
    assert response.tool_calls == []
