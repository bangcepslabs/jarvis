from abc import ABC, abstractmethod

from app.tts.models import SynthesisResult


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, language: str = "ko", speaker: int = 0, speed: float = 1.0) -> SynthesisResult:
        """Synthesize text to audio without persistence or side effects."""
