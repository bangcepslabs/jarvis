"""Test process defaults must win over any developer or server .env file."""
import os


os.environ.update({
    "APP_ENV": "test",
    "JARVIS_AUTH_ENABLED": "false",
    "JARVIS_CLIENT_TOKEN": "",
    "LLM_PROVIDER": "mock",
    "LLM_MODEL": "jarvis-test",
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "https://api.openai.com/v1/chat/completions",
    "TAVILY_API_KEY": "",
    "WEB_SEARCH_ENABLED": "false",
    "MEMORY_CURATOR_ENABLED": "false",
    "STT_PRELOAD": "false",
    "TTS_PRELOAD": "false",
    "VOICE_LATENCY_METRICS": "false",
})


def pytest_configure():
    from app.core.config import get_settings
    get_settings.cache_clear()
