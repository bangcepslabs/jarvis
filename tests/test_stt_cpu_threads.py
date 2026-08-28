import sys
import types

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.stt.faster_whisper_provider import FasterWhisperProvider


def test_stt_cpu_threads_defaults_to_ct2_default():
    assert Settings().stt_cpu_threads == 0


def test_stt_cpu_threads_reads_environment(monkeypatch):
    monkeypatch.setenv("STT_CPU_THREADS", "6")
    assert Settings().stt_cpu_threads == 6


def test_stt_cpu_threads_rejects_negative_values(monkeypatch):
    monkeypatch.setenv("STT_CPU_THREADS", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_provider_passes_cpu_threads_only_for_cpu(monkeypatch):
    calls = []

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            calls.append((model_name, kwargs))

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    FasterWhisperProvider(cpu_threads=6)._load_model()
    FasterWhisperProvider(device="cuda", cpu_threads=6)._load_model()

    assert calls[0][1]["cpu_threads"] == 6
    assert "cpu_threads" not in calls[1][1]
