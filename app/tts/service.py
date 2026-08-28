import asyncio
import logging

from app.tts.exceptions import TTSTextValidationError, TTSTimeoutError, TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.provider import TTSProvider
from app.agent.models import PresentationHint
from app.tts.profiles import VoiceProfile, VoiceProfiles

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self, provider: TTSProvider, max_text_chars: int = 1000, timeout_seconds: float = 60.0, max_concurrent_requests: int = 1, voice_profile: VoiceProfile | None = None) -> None:
        if max_text_chars < 1 or timeout_seconds <= 0 or max_concurrent_requests < 1:
            raise ValueError("Invalid TTS limits")
        self._provider = provider
        self._max_text_chars = max_text_chars
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._voice_profile = voice_profile or VoiceProfiles.supertonic_default

    async def synthesize(self, text: str, language: str = "ko", speaker: int | None = None, speed: float | None = None, presentation_hint: PresentationHint | None = None, voice_profile_id: str | None = None) -> SynthesisResult:
        if not text or not text.strip() or len(text) > self._max_text_chars:
            raise TTSTextValidationError("TTS text must be non-empty and within the configured length limit.")
        profile = VoiceProfiles.by_id(voice_profile_id) if voice_profile_id else self._voice_profile
        selected_speaker = profile.speaker_id if speaker is None else speaker
        selected_speed = speed if speed is not None else 1.0
        if selected_speed <= 0:
            raise TTSTextValidationError("TTS speed must be greater than zero.")
        async with self._semaphore:
            try:
                result = await asyncio.wait_for(self._provider.synthesize(text.strip(), language or profile.language, selected_speaker, selected_speed), timeout=self._timeout_seconds)
            except asyncio.TimeoutError as exc:
                logger.warning("tts_timeout provider=%s text_chars=%s", type(self._provider).__name__, len(text))
                raise TTSTimeoutError("Speech synthesis timed out.") from exc
            except (TTSTextValidationError, TTSTimeoutError):
                raise
            except Exception as exc:
                logger.warning("tts_provider_failed provider=%s error_type=%s", type(self._provider).__name__, type(exc).__name__)
                raise TTSProviderError("Speech synthesis is currently unavailable.") from exc
        return result
