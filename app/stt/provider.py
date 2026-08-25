from abc import ABC, abstractmethod

from app.stt.models import TranscriptionResult


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, filename: str | None = None) -> TranscriptionResult:
        """Transcribe audio bytes without persisting the source audio."""
