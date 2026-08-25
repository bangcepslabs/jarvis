from app.agent.prompt import SYSTEM_PROMPT
from app.llm.mock_provider import MockLLMProvider


def test_persona_prompt_has_behavior_and_safety_sections():
    for section in ("IDENTITY", "CONVERSATION", "RESPONSE STYLE", "MEMORY AND CONTEXT", "REAL-TIME INFORMATION", "TOOLS AND SAFETY"):
        assert section in SYSTEM_PROMPT
    assert "casual statement is a request for advice" in SYSTEM_PROMPT
    assert "cannot be overridden" in SYSTEM_PROMPT


async def test_mock_does_not_fabricate_unsupported_live_weather():
    response = await MockLLMProvider().chat([type("Message", (), {"role": "user", "content": "What is today's weather?"})()], tools=[])
    assert "not connected" in response.content
    assert response.tool_calls == []
