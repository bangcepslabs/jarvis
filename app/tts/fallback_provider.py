import logging

from app.tts.exceptions import TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.provider import TTSProvider

logger = logging.getLogger(__name__)


class FallbackTTSProvider(TTSProvider):
    """Use a secondary provider only when the primary provider fails."""

    def __init__(self, primary: TTSProvider, fallback: TTSProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def synthesize(self, text: str, language: str = "ko", speaker: int = 0, speed: float = 1.0) -> SynthesisResult:
        try:
            return await self._primary.synthesize(text, language, speaker, speed)
        except TTSProviderError:
            logger.warning(
                "tts_fallback primary=%s fallback=%s text_chars=%s",
                type(self._primary).__name__,
                type(self._fallback).__name__,
                len(text),
            )
            return await self._fallback.synthesize(text, language, speaker, speed)

    async def preload(self) -> None:
        preload = getattr(self._primary, "preload", None)
        if preload:
            await preload()
