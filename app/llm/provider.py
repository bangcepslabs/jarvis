from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_provider import OpenAICompatibleProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider.lower() == "mock":
        return MockLLMProvider()
    if settings.llm_provider.lower() in {"openai", "openai_compatible"}:
        try:
            return OpenAICompatibleProvider(settings)
        except Exception as exc:
            raise ConfigurationError("The configured LLM provider is unavailable.") from exc
    raise ConfigurationError(f"Unsupported LLM provider: {settings.llm_provider}.")
