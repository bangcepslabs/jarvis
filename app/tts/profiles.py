from dataclasses import dataclass
from typing import Literal

from app.agent.models import PresentationHint

VoiceStyle = Literal["neutral", "bright", "calm", "serious", "soft", "energetic"]


@dataclass(frozen=True)
class VoiceCapabilities:
    supports_speed: bool = True
    supports_pitch: bool = False
    supports_energy: bool = False
    supports_style: bool = False
    supports_speaker_selection: bool = True


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    display_name: str
    engine: str
    model_id: str
    language: str
    speaker_id: int
    default_style: VoiceStyle = "neutral"
    capabilities: VoiceCapabilities = VoiceCapabilities()
    emotion_styles: dict[str, VoiceStyle] = None

    def style_for(self, hint: PresentationHint | None) -> VoiceStyle:
        if not hint or not self.capabilities.supports_style:
            return self.default_style
        return (self.emotion_styles or {}).get(hint.emotion, self.default_style)


class VoiceProfiles:
    supertonic_default = VoiceProfile(
        id="supertonic_default", display_name="Supertonic Default", engine="sherpa_onnx",
        model_id="supertonic3", language="ko", speaker_id=0,
        emotion_styles={"happy": "bright", "excited": "energetic", "concerned": "calm", "thinking": "calm", "playful": "bright"},
    )

    @classmethod
    def by_id(cls, profile_id: str | None) -> VoiceProfile:
        return cls.supertonic_default if profile_id != cls.supertonic_default.id else cls.supertonic_default
