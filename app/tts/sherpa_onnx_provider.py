import asyncio
import io
import logging
import wave
from pathlib import Path

import numpy as np

from app.tts.exceptions import TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.provider import TTSProvider

logger = logging.getLogger(__name__)


class SherpaOnnxTTSProvider(TTSProvider):
    def __init__(self, model_dir: str, language: str = "ko", num_threads: int = 2) -> None:
        if not model_dir:
            raise TTSProviderError("TTS_MODEL_DIR is not configured.")
        self._model_dir = Path(model_dir)
        self._language = language
        self._num_threads = num_threads
        self._tts = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self):
        if self._tts is None:
            async with self._model_lock:
                if self._tts is None:
                    self._tts = await asyncio.to_thread(self._load_model)
        return self._tts

    async def preload(self) -> None:
        await self._get_model()

    def _load_model(self):
        try:
            import sherpa_onnx
            required = {
                name: self._model_dir / name for name in (
                    "duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
                    "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin",
                )
            }
            missing = [str(path.name) for path in required.values() if not path.exists()]
            if missing:
                raise FileNotFoundError(", ".join(missing))
            supertonic = sherpa_onnx.OfflineTtsSupertonicModelConfig(*(str(path) for path in required.values()))
            model = sherpa_onnx.OfflineTtsModelConfig(supertonic=supertonic, num_threads=self._num_threads, provider="cpu")
            config = sherpa_onnx.OfflineTtsConfig(model=model)
            if not config.validate():
                raise ValueError("invalid sherpa-onnx TTS configuration")
            return sherpa_onnx.OfflineTts(config)
        except Exception as exc:
            raise TTSProviderError("The local TTS model could not be loaded.") from exc

    async def synthesize(self, text: str, language: str = "ko", speaker: int = 0, speed: float = 1.0) -> SynthesisResult:
        if language != self._language:
            raise TTSProviderError("The configured local TTS provider supports only its configured language.")
        try:
            model = await self._get_model()
            result = await asyncio.to_thread(model.generate, text, int(speaker), float(speed))
            samples = np.asarray(result.samples, dtype=np.float32)
            if samples.size == 0 or result.sample_rate <= 0:
                raise ValueError("empty TTS output")
            pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(int(result.sample_rate))
                output.writeframes(pcm.tobytes())
            return SynthesisResult(audio_bytes=buffer.getvalue(), sample_rate=int(result.sample_rate), duration_seconds=float(samples.size / result.sample_rate), provider="sherpa_onnx_supertonic3")
        except TTSProviderError:
            raise
        except Exception as exc:
            raise TTSProviderError("The local TTS synthesis failed.") from exc
