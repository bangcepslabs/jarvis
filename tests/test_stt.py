import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.stt.exceptions import AudioTooLargeError, STTProviderError, STTTimeoutError
from app.stt.models import TranscriptionResult
from app.stt.service import STTService
from app.api.dependencies import get_stt_service
from app.core.config import get_settings


class FakeSTT:
    def __init__(self, result=None, error=None):
        self.result = result or TranscriptionResult(text="오늘 부산 날씨 어때?", language="ko", language_probability=0.98, duration_seconds=2.7)
        self.error = error

    async def transcribe(self, audio, filename=None):
        if self.error:
            raise self.error
        return self.result


@pytest.mark.asyncio
async def test_stt_service_transcribes_and_handles_empty():
    service = STTService(FakeSTT(), max_file_mb=1, timeout_seconds=1)
    result = await service.transcribe(b"wav", "sample.wav")
    assert result.text.startswith("오늘")
    empty = await service.transcribe(b"")
    assert empty.text == "" and empty.speech_detected is False


@pytest.mark.asyncio
async def test_stt_service_preserves_provider_timings():
    result = TranscriptionResult(
        text="ok",
        timings_ms={"temp_file_write_ms": 2, "inference_ms": 42},
    )
    measured = await STTService(FakeSTT(result=result), timeout_seconds=1).transcribe(b"wav", "sample.wav")
    assert measured.timings_ms is not None
    assert measured.timings_ms["temp_file_write_ms"] == 2
    assert measured.timings_ms["inference_ms"] == 42
    assert measured.timings_ms["queue_wait_ms"] >= 0


@pytest.mark.asyncio
async def test_stt_service_file_size_and_timeout():
    with pytest.raises(AudioTooLargeError):
        await STTService(FakeSTT(), max_file_mb=1).transcribe(b"x" * (1024 * 1024 + 1))

    class Slow:
        async def transcribe(self, audio, filename=None):
            await asyncio.sleep(0.05)

    with pytest.raises(STTTimeoutError):
        await STTService(Slow(), timeout_seconds=0.001).transcribe(b"audio")


@pytest.mark.asyncio
async def test_stt_provider_failure_is_safe():
    with pytest.raises(STTProviderError):
        await STTService(FakeSTT(error=RuntimeError("decode"))).transcribe(b"audio")


def test_stt_endpoint_disabled_is_safe(monkeypatch):
    monkeypatch.setenv("STT_ENABLED", "false")
    get_settings.cache_clear()
    get_stt_service.cache_clear()
    response = TestClient(app).post("/api/stt/transcribe", files={"file": ("sample.wav", b"audio", "audio/wav")})
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
