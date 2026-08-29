from functools import lru_cache

from app.actions.service import ActionConfirmationService
from app.agent.jarvis_agent import JarvisAgent
from app.agent.tool_router import ToolRouter
from app.core.config import get_settings
from app.llm.provider import create_llm_provider
from app.services.chat_service import ChatService
from app.services.docker_service import DockerService
from app.memory.service import MemoryService
from app.memory.sqlite_store import SQLiteMemoryStore
from app.memory.curator import MemoryCurator
from app.conversation.store import SQLiteConversationStore
from app.conversation.context import ConversationContextManager
from app.conversation.summary import ConversationSummarizer, SQLiteConversationSummaryStore
from app.llm.calibration import LLMCalibrationCollector
from app.tools.docker.tools import GetContainerLogsTool, GetContainerStatusTool, ListContainersTool
from app.tools.docker.restart import RestartContainerTool
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.system.status import SystemStatusTool
from app.tools.system.time import CurrentTimeTool
from app.weather.open_meteo import OpenMeteoProvider
from app.weather.service import WeatherService
from app.weather.tools import CurrentWeatherTool, WeatherForecastTool
from app.search.service import SearchService
from app.search.tavily import TavilySearchProvider
from app.search.tools import NewsSearchTool, WebSearchTool
from app.stt.exceptions import STTDisabledError
from app.stt.faster_whisper_provider import FasterWhisperProvider
from app.stt.service import STTService
from app.stt.sample_capture import STTSampleCapture
from app.tts.exceptions import TTSEnabledError
from app.tts.service import TTSService
from app.tts.profiles import VoiceProfiles
from app.tts.factory import create_tts_provider


@lru_cache
def get_chat_service() -> ChatService:
    registry = ToolRegistry()
    registry.register(CurrentTimeTool())
    registry.register(SystemStatusTool())
    docker_service = DockerService()
    registry.register(ListContainersTool(docker_service))
    registry.register(GetContainerStatusTool(docker_service))
    registry.register(GetContainerLogsTool(docker_service))
    registry.register(RestartContainerTool(docker_service, get_settings().docker_restart_timeout_seconds))
    executor = ToolExecutor(registry)
    actions = ActionConfirmationService(ttl_seconds=get_settings().action_confirmation_ttl_seconds)
    settings = get_settings()
    if settings.weather_enabled:
        weather_service = WeatherService(OpenMeteoProvider(settings.weather_timeout_seconds), settings.weather_default_location)
        registry.register(CurrentWeatherTool(weather_service))
        registry.register(WeatherForecastTool(weather_service, settings.weather_forecast_max_days))
    if settings.web_search_enabled and settings.search_provider.lower() == "tavily" and settings.tavily_api_key:
        search_service = SearchService(TavilySearchProvider(settings.tavily_api_key, settings.tavily_base_url, settings.search_timeout_seconds), settings.search_max_results)
        registry.register(WebSearchTool(search_service))
        registry.register(NewsSearchTool(search_service))
    memory = None
    if settings.memory_enabled:
        memory = MemoryService(
            SQLiteMemoryStore(settings.memory_database_path),
            max_context_items=settings.memory_max_context_items,
            max_item_chars=settings.memory_max_item_chars,
            max_context_chars=settings.memory_max_context_chars,
        )
    conversations = SQLiteConversationStore(settings.memory_database_path, settings.conversation_store_max_messages) if settings.conversation_enabled else None
    provider = create_llm_provider(settings)
    calibration = LLMCalibrationCollector()
    curator = MemoryCurator(provider, memory, settings) if memory and settings.memory_curator_enabled else None
    return ChatService(
        JarvisAgent(
            provider, executor, registry, actions, memory,
            conversations, settings.conversation_max_messages, settings.conversation_max_context_chars,
            ToolRouter(provider, registry, settings, calibration),
            curator,
            ConversationContextManager(
                max_tokens=settings.conversation_context_max_tokens,
                min_recent_turns=settings.conversation_context_min_recent_turns,
                system_reserve=settings.conversation_context_system_reserve,
                tool_reserve=settings.conversation_context_tool_reserve,
                output_reserve=settings.conversation_context_output_reserve,
            ),
            SQLiteConversationSummaryStore(settings.memory_database_path),
            ConversationSummarizer(provider, settings.conversation_summary_max_tokens, settings.llm_summary_model),
            settings.conversation_summary_enabled,
            settings.conversation_summary_min_new_turns,
            calibration,
        )
    )


@lru_cache
def get_stt_service() -> STTService:
    settings = get_settings()
    if not settings.stt_enabled:
        raise STTDisabledError("Speech transcription is disabled.")
    if settings.stt_provider.lower() != "faster_whisper":
        raise STTDisabledError("The configured speech provider is unavailable.")
    return STTService(
        FasterWhisperProvider(
            model=settings.stt_model,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
            language=settings.stt_language,
            beam_size=settings.stt_beam_size,
            best_of=settings.stt_best_of,
            patience=settings.stt_patience,
            temperature=settings.stt_temperature,
            vad_filter=settings.stt_vad_filter,
            vad_min_silence_duration_ms=settings.stt_vad_min_silence_duration_ms,
            vad_speech_pad_ms=settings.stt_vad_speech_pad_ms,
            vad_threshold=settings.stt_vad_threshold,
            bias_terms=settings.stt_bias_terms,
            bias_prompt_max_chars=settings.stt_bias_prompt_max_chars,
            transcript_correction_enabled=settings.stt_transcript_correction_enabled,
            known_terms=settings.stt_known_terms,
            cpu_threads=settings.stt_cpu_threads,
            cache_dir=settings.stt_model_cache_dir,
            temp_dir=settings.temp_dir,
        ),
        max_file_mb=settings.stt_max_file_mb,
        timeout_seconds=settings.stt_timeout_seconds,
        max_concurrent_requests=settings.stt_max_concurrent_requests,
        sample_capture=STTSampleCapture(
            enabled=settings.stt_sample_capture_enabled,
            directory=settings.stt_sample_capture_dir,
            max_files=settings.stt_sample_capture_max_files,
            language=settings.stt_language,
            model=settings.stt_model,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
        ),
    )


@lru_cache
def get_tts_service() -> TTSService:
    settings = get_settings()
    if not settings.tts_enabled:
        raise TTSEnabledError("Speech synthesis is disabled.")
    return TTSService(
        create_tts_provider(settings),
        max_text_chars=settings.tts_max_text_chars,
        timeout_seconds=settings.tts_timeout_seconds,
        max_concurrent_requests=settings.tts_max_concurrent_requests,
        voice_profile=VoiceProfiles.by_id(settings.tts_voice_profile),
    )
