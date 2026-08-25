import asyncio
import wave
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tts.exceptions import TTSTextValidationError, TTSTimeoutError, TTSProviderError
from app.tts.models import SynthesisResult
from app.tts.service import TTSService


class FakeTTS:
    async def synthesize(self, text, language="ko", speaker=0, speed=1.0):
        buffer = BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000); output.writeframes(b"\0\0" * 1600)
        return SynthesisResult(audio_bytes=buffer.getvalue(), sample_rate=16000, duration_seconds=0.1, provider="fake")


@pytest.mark.asyncio
async def test_tts_service_success_and_validation():
    service = TTSService(FakeTTS(), max_text_chars=10, timeout_seconds=1)
    result = await service.synthesize("안녕하세요")
    assert result.media_type == "audio/wav" and result.sample_rate == 16000
    with pytest.raises(TTSTextValidationError):
        await service.synthesize(" ")
    with pytest.raises(TTSTextValidationError):
        await service.synthesize("12345678901")


@pytest.mark.asyncio
async def test_tts_service_timeout_and_provider_failure():
    class Slow:
        async def synthesize(self, *args):
            await asyncio.sleep(0.05)
    with pytest.raises(TTSTimeoutError):
        await TTSService(Slow(), timeout_seconds=0.001).synthesize("hi")

    class Broken:
        async def synthesize(self, *args):
            raise RuntimeError("broken")
    with pytest.raises(TTSProviderError):
        await TTSService(Broken()).synthesize("hi")


def test_tts_endpoint_disabled_is_safe(monkeypatch):
    from app.api.routes import tts as tts_route
    from app.tts.exceptions import TTSEnabledError
    monkeypatch.setattr(tts_route, "get_tts_service", lambda: (_ for _ in ()).throw(TTSEnabledError("Speech synthesis is disabled.")))
    response = TestClient(app).post("/api/tts/synthesize", json={"text": "안녕하세요"})
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
