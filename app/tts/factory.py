from app.core.config import Settings
from app.tts.exceptions import TTSEnabledError
from app.tts.fallback_provider import FallbackTTSProvider
from app.tts.gpt_sovits_provider import GPTSoVITSTTSProvider
from app.tts.provider import TTSProvider
from app.tts.sherpa_onnx_provider import SherpaOnnxTTSProvider


def create_tts_provider(settings: Settings) -> TTSProvider:
    def supertonic() -> TTSProvider:
        return SherpaOnnxTTSProvider(
            settings.tts_model_dir or "",
            settings.tts_language,
            settings.tts_num_threads,
        )

    provider_name = settings.tts_provider.strip().lower()
    if provider_name in {"supertonic", "sherpa_onnx"}:
        return supertonic()
    if provider_name == "gpt_sovits":
        primary = GPTSoVITSTTSProvider(
            settings.gpt_sovits_base_url,
            settings.gpt_sovits_timeout_seconds,
            text_lang=settings.gpt_sovits_text_lang,
            prompt_lang=settings.gpt_sovits_prompt_lang,
            ref_audio_path=settings.gpt_sovits_ref_audio_path,
            prompt_text=settings.gpt_sovits_prompt_text,
            speed_factor=settings.gpt_sovits_speed_factor,
            text_split_method=settings.gpt_sovits_text_split_method,
        )
        return FallbackTTSProvider(primary, supertonic()) if settings.gpt_sovits_fallback_to_supertonic else primary
    raise TTSEnabledError("The configured speech provider is unavailable.")
