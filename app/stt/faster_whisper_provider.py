import asyncio
import logging
import tempfile
import time
from pathlib import Path

from app.stt.exceptions import STTProviderError
from app.stt.models import TranscriptionResult, TranscriptSegment
from app.stt.provider import STTProvider

logger = logging.getLogger(__name__)


class FasterWhisperProvider(STTProvider):
    def __init__(self, model: str = "small", device: str = "cpu", compute_type: str = "int8", language: str | None = None, beam_size: int = 1, vad_filter: bool = True, cache_dir: str | None = None, temp_dir: str | None = None) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._language = language or None
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._cache_dir = cache_dir
        self._temp_dir = temp_dir
        self._model = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self):
        if self._model is None:
            async with self._model_lock:
                if self._model is None:
                    self._model = await asyncio.to_thread(self._load_model)
        return self._model

    async def preload(self) -> None:
        await self._get_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            kwargs = {"device": self._device, "compute_type": self._compute_type}
            if self._cache_dir:
                kwargs["download_root"] = self._cache_dir
            return WhisperModel(self._model_name, **kwargs)
        except Exception as exc:
            raise STTProviderError("The speech model could not be loaded.") from exc

    async def transcribe(self, audio: bytes, filename: str | None = None) -> TranscriptionResult:
        suffix = Path(filename or "audio.wav").suffix or ".wav"
        timings_ms: dict[str, int] = {}
        try:
            if self._temp_dir:
                Path(self._temp_dir).mkdir(parents=True, exist_ok=True)
            file_started = time.perf_counter()
            with tempfile.NamedTemporaryFile(prefix="jarvis-stt-", suffix=suffix, dir=self._temp_dir, delete=False) as handle:
                path = Path(handle.name)
                handle.write(audio)
            timings_ms["temp_file_write_ms"] = round((time.perf_counter() - file_started) * 1000)
            try:
                model_started = time.perf_counter()
                model_reused = self._model is not None
                model = await self._get_model()
                timings_ms["model_acquire_ms"] = round((time.perf_counter() - model_started) * 1000)
                inference_started = time.perf_counter()
                result = await asyncio.to_thread(self._transcribe_file, model, path)
                timings_ms["inference_ms"] = round((time.perf_counter() - inference_started) * 1000)
                timings_ms["model_reused"] = int(model_reused)
                return result.model_copy(update={"timings_ms": timings_ms})
            finally:
                path.unlink(missing_ok=True)
        except STTProviderError:
            raise
        except Exception as exc:
            raise STTProviderError("The audio could not be transcribed.") from exc

    def _transcribe_file(self, model, path: Path) -> TranscriptionResult:
        segments, info = model.transcribe(str(path), language=self._language, beam_size=self._beam_size, vad_filter=self._vad_filter)
        collected = []
        texts = []
        for segment in segments:
            text = segment.text or ""
            texts.append(text)
            collected.append(TranscriptSegment(start=float(segment.start), end=float(segment.end), text=text))
        return TranscriptionResult(
            text="".join(texts).strip(),
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            duration_seconds=getattr(info, "duration", None),
            speech_detected=bool("".join(texts).strip()),
            segments=collected or None,
        )
