from abc import ABC, abstractmethod

from app.agent.models import ChatMessage
from app.llm.models import LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, object]] | None = None, tool_choice: str | dict[str, object] | None = None, response_format: dict[str, object] | None = None, **kwargs) -> LLMResponse:
        """Return an assistant response for the supplied conversation."""
