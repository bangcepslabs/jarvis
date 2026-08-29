import types

from app.stt.context import build_initial_prompt, correct_transcript, parse_terms
from app.stt.faster_whisper_provider import FasterWhisperProvider


def test_bias_terms_are_trimmed_deduplicated_and_empty_values_removed():
    assert parse_terms(" 자비스,,JARVIS,자비스, Docker ") == ["자비스", "JARVIS", "Docker"]


def test_initial_prompt_is_optional_and_bounded():
    assert build_initial_prompt(" , ") is None
    prompt = build_initial_prompt("alpha,beta,gamma", max_chars=10)
    assert prompt == "alpha"


def test_transcript_correction_is_disabled_or_only_uses_registered_aliases():
    assert correct_transcript("이미치 일반문장", None) == "이미치 일반문장"
    assert correct_transcript("이미치 일반문장", {"Immich": ["이미치"]}) == "Immich 일반문장"
    assert correct_transcript("일반 문장", {"Immich": ["이미치"]}) == "일반 문장"


def test_provider_passes_optional_decoding_and_vad_settings(tmp_path):
    calls = []

    class FakeModel:
        def transcribe(self, path, **kwargs):
            calls.append(kwargs)
            segment = types.SimpleNamespace(start=0, end=1, text="ok")
            info = types.SimpleNamespace(language="ko", language_probability=1.0, duration=1.0)
            return [segment], info

    provider = FasterWhisperProvider(
        language="ko",
        beam_size=5,
        best_of=3,
        patience=1.2,
        temperature=0.0,
        vad_min_silence_duration_ms=500,
        vad_speech_pad_ms=200,
        vad_threshold=0.5,
        bias_terms="JARVIS,Docker,JARVIS",
        transcript_correction_enabled=False,
    )
    provider._transcribe_file(FakeModel(), tmp_path / "sample.wav")
    assert calls == [{
        "language": "ko", "beam_size": 5, "vad_filter": True,
        "best_of": 3, "patience": 1.2, "temperature": 0.0,
        "initial_prompt": "JARVIS, Docker",
        "vad_parameters": {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
            "threshold": 0.5,
        },
    }]
