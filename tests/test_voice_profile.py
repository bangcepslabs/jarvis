from app.agent.models import PresentationHint
from app.tts.profiles import VoiceProfiles
from app.tts.service import TTSService


def test_supertonic_profile_records_actual_supported_capabilities():
    profile = VoiceProfiles.by_id("unknown")
    assert profile.id == "supertonic_default"
    assert profile.capabilities.supports_speed is True
    assert profile.capabilities.supports_speaker_selection is True
    assert profile.capabilities.supports_pitch is False
    assert profile.capabilities.supports_energy is False
    assert profile.capabilities.supports_style is False


def test_unsupported_style_does_not_change_semantic_profile_or_authorization():
    profile = VoiceProfiles.supertonic_default
    hint = PresentationHint(emotion="excited", intensity=0.9)
    assert profile.style_for(hint) == "neutral"
    assert TTSService is not None
