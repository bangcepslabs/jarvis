import io
import wave

import httpx
import pytest

from app.core.config import Settings
from app.tts.exceptions import TTSProviderError
from app.tts.factory import create_tts_provider
from app.tts.fallback_provider import FallbackTTSProvider
from app.tts.gpt_sovits_provider import GPTSoVITSTTSProvider
from app.tts.models import SynthesisResult
from app.tts.sherpa_onnx_provider import SherpaOnnxTTSProvider


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 1600)
    return buffer.getvalue()


class FakeClient:
    def __init__(self, response=None, error=None, **kwargs):
        self.response = response
        self.error = error
        self.kwargs = kwargs
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json):
        self.calls.append((url, json))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_gpt_sovits_provider_posts_text_and_parses_wav():
    request = httpx.Request("POST", "http://gpt-sovits/tts")
    client = FakeClient(response=httpx.Response(200, content=wav_bytes(), request=request))
    provider = GPTSoVITSTTSProvider(
        "http://gpt-sovits",
        ref_audio_path="/voices/ref.wav",
        prompt_text="reference",
        client_factory=lambda **kwargs: client,
    )

    result = await provider.synthesize("hello")

    assert client.calls == [(
        "http://gpt-sovits/tts",
        {
            "text": "hello",
            "text_lang": "ko",
            "ref_audio_path": "/voices/ref.wav",
            "prompt_lang": "ja",
            "prompt_text": "reference",
            "media_type": "wav",
            "streaming_mode": False,
            "speed_factor": 1.0,
            "text_split_method": "cut5",
        },
    )]
    assert result.provider == "gpt_sovits_http"
    assert result.sample_rate == 16000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client",
    [
        FakeClient(error=httpx.ReadTimeout("timed out")),
        FakeClient(response=httpx.Response(500, request=httpx.Request("POST", "http://gpt-sovits/tts"))),
    ],
)
async def test_gpt_sovits_provider_maps_network_and_server_failures(client):
    provider = GPTSoVITSTTSProvider("http://gpt-sovits", ref_audio_path="/voices/ref.wav", client_factory=lambda **kwargs: client)
    with pytest.raises(TTSProviderError):
        await provider.synthesize("hello")


@pytest.mark.asyncio
async def test_fallback_provider_uses_supertonic_after_primary_failure():
    class Broken:
        async def synthesize(self, *args):
            raise TTSProviderError("unavailable")

    class Working:
        async def synthesize(self, *args):
            return SynthesisResult(audio_bytes=wav_bytes(), sample_rate=16000, duration_seconds=0.1, provider="supertonic")

    result = await FallbackTTSProvider(Broken(), Working()).synthesize("hello")
    assert result.provider == "supertonic"


def test_provider_factory_defaults_to_supertonic_and_selects_gpt_sovits():
    default = create_tts_provider(Settings(tts_model_dir="models"))
    gpt_sovits = create_tts_provider(Settings(tts_provider="gpt_sovits", gpt_sovits_ref_audio_path="/voices/ref.wav"))
    fallback = create_tts_provider(
        Settings(
            tts_provider="gpt_sovits",
            tts_model_dir="models",
            gpt_sovits_fallback_to_supertonic=True,
            gpt_sovits_ref_audio_path="/voices/ref.wav",
        )
    )

    assert isinstance(default, SherpaOnnxTTSProvider)
    assert isinstance(gpt_sovits, GPTSoVITSTTSProvider)
    assert isinstance(fallback, FallbackTTSProvider)
