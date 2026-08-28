import asyncio
import logging
import time

from app.stt.exceptions import AudioTooLargeError, STTDisabledError, STTProviderError, STTTimeoutError
from app.stt.models import TranscriptionResult
from app.stt.provider import STTProvider

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self, provider: STTProvider, max_file_mb: int = 20, timeout_seconds: float = 60.0, max_concurrent_requests: int = 1) -> None:
        if max_file_mb < 1 or timeout_seconds <= 0 or max_concurrent_requests < 1:
            raise ValueError("Invalid STT limits")
        self._provider = provider
        self._max_bytes = max_file_mb * 1024 * 1024
        self._timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def transcribe(self, audio: bytes, filename: str | None = None) -> TranscriptionResult:
        if len(audio) > self._max_bytes:
            raise AudioTooLargeError("The audio file is too large.")
        if not audio:
            return TranscriptionResult(text="", speech_detected=False)
        queued_at = time.perf_counter()
        async with self._semaphore:
            queue_wait_ms = round((time.perf_counter() - queued_at) * 1000)
            try:
                result = await asyncio.wait_for(self._provider.transcribe(audio, filename), timeout=self._timeout)
            except asyncio.TimeoutError as exc:
                logger.warning("stt_timeout provider=%s", type(self._provider).__name__)
                raise STTTimeoutError("Speech transcription timed out.") from exc
            except (STTTimeoutError, AudioTooLargeError):
                raise
            except Exception as exc:
                logger.warning("stt_provider_failed provider=%s error_type=%s", type(self._provider).__name__, type(exc).__name__)
                raise STTProviderError("Speech transcription is currently unavailable.") from exc
        timings_ms = {**(result.timings_ms or {}), "queue_wait_ms": queue_wait_ms}
        if not result.text.strip():
            return result.model_copy(update={"text": "", "speech_detected": False, "timings_ms": timings_ms})
        return result.model_copy(update={"timings_ms": timings_ms})

    async def preload(self) -> None:
        preload = getattr(self._provider, "preload", None)
        if preload:
            await preload()
