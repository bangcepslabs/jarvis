import json
import wave
from io import BytesIO

import pytest

from app.stt.models import TranscriptionResult
from app.stt.sample_capture import STTSampleCapture
from app.stt.service import STTService
from app.core.config import Settings


def wav_bytes() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 800)
    return output.getvalue()


def test_sample_capture_config_defaults_and_environment(monkeypatch):
    assert Settings(_env_file=None).stt_sample_capture_enabled is False
    monkeypatch.setenv("STT_SAMPLE_CAPTURE_ENABLED", "true")
    monkeypatch.setenv("STT_SAMPLE_CAPTURE_DIR", "custom/samples")
    monkeypatch.setenv("STT_SAMPLE_CAPTURE_MAX_FILES", "7")
    settings = Settings(_env_file=None)
    assert settings.stt_sample_capture_enabled is True
    assert settings.stt_sample_capture_dir == "custom/samples"
    assert settings.stt_sample_capture_max_files == 7


class FakeProvider:
    async def transcribe(self, audio, filename=None):
        return TranscriptionResult(text="테스트", language="ko", duration_seconds=0.1)


@pytest.mark.asyncio
async def test_capture_disabled_writes_nothing(tmp_path):
    capture = STTSampleCapture(False, str(tmp_path), 2, "ko", "small", "cpu", "int8")
    await STTService(FakeProvider(), sample_capture=capture).transcribe(wav_bytes(), "input.wav")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_capture_writes_unique_wav_and_manifest(tmp_path):
    capture = STTSampleCapture(True, str(tmp_path), 2, "ko", "small", "cuda", "float16")
    service = STTService(FakeProvider(), sample_capture=capture)
    audio = wav_bytes()
    await service.transcribe(audio, "input.wav")
    await service.transcribe(audio, "input.wav")
    wavs = list(tmp_path.glob("*.wav"))
    assert len(wavs) == 2 and wavs[0].name != wavs[1].name
    records = [json.loads(line) for line in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["expected_transcript"] is None
    assert records[0]["raw_transcript"] == "테스트"


@pytest.mark.asyncio
async def test_capture_stops_at_max_without_failing_stt(tmp_path):
    capture = STTSampleCapture(True, str(tmp_path), 1, "ko", "small", "cpu", "int8")
    service = STTService(FakeProvider(), sample_capture=capture)
    audio = wav_bytes()
    await service.transcribe(audio)
    result = await service.transcribe(audio)
    assert result.text == "테스트"
    assert len(list(tmp_path.glob("*.wav"))) == 1


@pytest.mark.asyncio
async def test_capture_failure_does_not_fail_stt(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    capture = STTSampleCapture(True, str(blocked), 1, "ko", "small", "cpu", "int8")
    result = await STTService(FakeProvider(), sample_capture=capture).transcribe(b"audio")
    assert result.text == "테스트"
