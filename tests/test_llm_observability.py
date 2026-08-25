import pytest

from app.agent.models import ChatMessage
from app.core.config import Settings
from app.llm.exceptions import LLMRateLimitError
from app.llm.openai_provider import OpenAICompatibleProvider


class Response:
    status_code = 200
    headers = {
        "x-ratelimit-remaining-requests": "9",
        "x-ratelimit-remaining-tokens": "800",
        "x-ratelimit-reset-requests": "1m",
        "retry-after": "20",
    }

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "ok", "tool_calls": []}}], "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}


class Client:
    last_payload = None
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def post(self, *args, **kwargs):
        Client.last_payload = kwargs.get("json")
        return Response()


@pytest.mark.asyncio
async def test_usage_and_rate_limit_metadata_are_parsed(monkeypatch):
    import app.llm.openai_provider as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: Client())
    result = await OpenAICompatibleProvider(Settings(llm_api_key="secret", llm_model="test")).chat([ChatMessage(role="user", content="hi")])
    assert result.usage.total_tokens == 14
    assert result.rate_limit.remaining_tokens == 800
    assert result.rate_limit.retry_after == "20"


@pytest.mark.asyncio
async def test_provider_maps_reasoning_budget_and_tool_choice(monkeypatch):
    import app.llm.openai_provider as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: Client())
    provider = OpenAICompatibleProvider(Settings(llm_api_key="secret", llm_model="test", llm_reasoning_effort="none", llm_max_completion_tokens=768))
    await provider.chat([ChatMessage(role="user", content="weather")], tools=[{"name": "get_current_weather"}], tool_choice="auto")
    assert Client.last_payload["reasoning_effort"] == "none"
    assert Client.last_payload["max_completion_tokens"] == 768
    assert Client.last_payload["tool_choice"] == "auto"


class RateLimitResponse(Response):
    status_code = 429


class RateLimitClient(Client):
    async def post(self, *args, **kwargs): return RateLimitResponse()


@pytest.mark.asyncio
async def test_429_maps_to_safe_rate_limit_error(monkeypatch):
    import app.llm.openai_provider as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: RateLimitClient())
    with pytest.raises(LLMRateLimitError) as error:
        await OpenAICompatibleProvider(Settings(llm_api_key="secret", llm_model="test")).chat([ChatMessage(role="user", content="hi")])
    assert error.value.rate_limit.retry_after == "20"
    assert "secret" not in str(error.value)
