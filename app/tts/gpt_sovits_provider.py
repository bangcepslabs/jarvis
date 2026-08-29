import io
import logging
import time
import wave
from collections.abc import Callable

import httpx

from app.tts.exceptions import TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.provider import TTSProvider

logger = logging.getLogger(__name__)


class GPTSoVITSTTSProvider(TTSProvider):
    """HTTP adapter for a separately deployed GPT-SoVITS service.

    The service contract is POST {base_url}/tts with a JSON ``text`` field and
    an ``audio/wav`` response. GPT-SoVITS itself remains outside JARVIS's
    Python environment.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        *,
        text_lang: str = "ko",
        prompt_lang: str = "ja",
        ref_audio_path: str = "",
        prompt_text: str = "",
        speed_factor: float = 1.0,
        text_split_method: str = "cut5",
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        if not base_url.strip():
            raise TTSProviderError("GPT_SOVITS_BASE_URL is not configured.")
        self._endpoint = f"{base_url.rstrip('/')}/tts"
        self._timeout_seconds = timeout_seconds
        self._text_lang = text_lang
        self._prompt_lang = prompt_lang
        self._ref_audio_path = ref_audio_path
        self._prompt_text = prompt_text
        self._speed_factor = speed_factor
        self._text_split_method = text_split_method
        self._client_factory = client_factory

    async def synthesize(self, text: str, language: str = "ko", speaker: int = 0, speed: float = 1.0) -> SynthesisResult:
        del speaker, speed
        if not self._ref_audio_path.strip():
            raise TTSProviderError("GPT_SOVITS_REF_AUDIO_PATH is not configured.")
        payload = {
            "text": text,
            "text_lang": self._text_lang or language or "ko",
            "ref_audio_path": self._ref_audio_path,
            "prompt_lang": self._prompt_lang,
            "prompt_text": self._prompt_text,
            "media_type": "wav",
            "streaming_mode": False,
            "speed_factor": self._speed_factor,
            "text_split_method": self._text_split_method,
        }
        started = time.perf_counter()
        try:
            async with self._client_factory(timeout=self._timeout_seconds) as client:
                response = await client.post(self._endpoint, json=payload)
                response.raise_for_status()
                audio = response.content
                content_type = response.headers.get("content-type", "")
                status_code = response.status_code
            logger.info(
                "gpt_sovits_request provider=gpt_sovits_http status=%s content_type=%s elapsed_ms=%s output_bytes=%s",
                status_code,
                content_type.split(";", 1)[0],
                round((time.perf_counter() - started) * 1000),
                len(audio),
            )
            if len(audio) < 12 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
                raise ValueError("invalid WAV header")
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if wav.getnframes() <= 0 or wav.getframerate() <= 0:
                    raise ValueError("empty WAV response")
                duration_seconds = wav.getnframes() / wav.getframerate()
                sample_rate = wav.getframerate()
            return SynthesisResult(
                audio_bytes=audio,
                sample_rate=sample_rate,
                duration_seconds=duration_seconds,
                provider="gpt_sovits_http",
            )
        except (httpx.HTTPError, wave.Error, ValueError) as exc:
            logger.warning(
                "gpt_sovits_request_failed provider=gpt_sovits_http category=%s elapsed_ms=%s",
                type(exc).__name__,
                round((time.perf_counter() - started) * 1000),
            )
            raise TTSProviderError("The GPT-SoVITS service could not synthesize speech.") from exc
