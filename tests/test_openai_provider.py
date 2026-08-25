import pytest

from app.agent.models import ChatMessage
from app.core.config import Settings
from app.llm.openai_provider import OpenAICompatibleProvider


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {"id": "call-1", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}
                        ],
                    },
                }
            ]
        }


class FakeAsyncClient:
    last_payload: dict[str, object] | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> FakeResponse:
        FakeAsyncClient.last_payload = kwargs["json"]
        assert url.endswith("/chat/completions")
        return FakeResponse()


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_native_tool_call(monkeypatch) -> None:
    import app.llm.openai_provider as module

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(Settings(llm_api_key="test-key", llm_model="test-model"))
    response = await provider.chat([ChatMessage(role="user", content="What time is it?")], tools=[])
    assert response.tool_calls[0].name == "get_current_time"
    assert response.tool_calls[0].arguments == {}
    assert FakeAsyncClient.last_payload["model"] == "test-model"
    assert FakeAsyncClient.last_payload["tools"] == []
    assert FakeAsyncClient.last_payload["tool_choice"] == "none"
