from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JARVIS"
    app_version: str = "0.5.2"
    app_env: str = "development"
    llm_provider: str = "mock"
    llm_model: str = "jarvis-development"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_reasoning_effort: str | None = "none"
    llm_max_completion_tokens: int = 768
    llm_temperature: float = 0.3
    llm_router_model: str | None = None
    llm_router_reasoning_effort: str | None = None
    llm_router_reasoning_format: str | None = None
    llm_router_temperature: float = 0.0
    llm_router_max_completion_tokens: int = 64
    action_confirmation_ttl_seconds: int = 300
    docker_restart_timeout_seconds: int = 10
    memory_database_path: str = "data/jarvis.db"
    memory_enabled: bool = True
    memory_max_context_items: int = 5
    memory_max_item_chars: int = 500
    memory_max_context_chars: int = 4000
    memory_curator_enabled: bool = False
    memory_curator_model: str | None = None
    memory_curator_reasoning_effort: str | None = None
    memory_curator_reasoning_format: str | None = None
    memory_curator_temperature: float = 0.0
    memory_curator_max_completion_tokens: int = 128
    memory_curator_timeout_seconds: float = 5.0
    conversation_enabled: bool = True
    conversation_max_messages: int = 10
    conversation_max_context_chars: int = 9000
    conversation_store_max_messages: int = 50
    weather_enabled: bool = True
    weather_default_location: str | None = None
    weather_timeout_seconds: float = 5.0
    weather_forecast_max_days: int = 7
    web_search_enabled: bool = True
    search_provider: str = "tavily"
    tavily_api_key: str | None = None
    tavily_base_url: str = "https://api.tavily.com"
    search_timeout_seconds: float = 8.0
    search_max_results: int = 5
    log_level: str = "INFO"
    stt_enabled: bool = False
    stt_provider: str = "faster_whisper"
    stt_model: str = "small"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_language: str | None = None
    stt_beam_size: int = 1
    stt_vad_filter: bool = True
    stt_timeout_seconds: float = 60.0
    stt_max_file_mb: int = 20
    stt_max_concurrent_requests: int = 1
    stt_model_cache_dir: str | None = None
    tts_enabled: bool = False
    tts_provider: str = "sherpa_onnx"
    tts_model: str = "supertonic3"
    tts_model_dir: str | None = None
    tts_language: str = "ko"
    tts_device: str = "cpu"
    tts_timeout_seconds: float = 60.0
    tts_max_text_chars: int = 1000
    tts_max_concurrent_requests: int = 1
    tts_num_threads: int = 2
    tts_speed: float = 1.0
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
