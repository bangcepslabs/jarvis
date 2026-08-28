import io
import wave
from collections.abc import Callable

import httpx

from app.tts.exceptions import TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.provider import TTSProvider


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
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        if not base_url.strip():
            raise TTSProviderError("GPT_SOVITS_BASE_URL is not configured.")
        self._endpoint = f"{base_url.rstrip('/')}/tts"
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory

    async def synthesize(self, text: str, language: str = "ko", speaker: int = 0, speed: float = 1.0) -> SynthesisResult:
        del language, speaker, speed
        try:
            async with self._client_factory(timeout=self._timeout_seconds) as client:
                response = await client.post(self._endpoint, json={"text": text})
                response.raise_for_status()
                audio = response.content
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
            raise TTSProviderError("The GPT-SoVITS service could not synthesize speech.") from exc
