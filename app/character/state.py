from dataclasses import dataclass, field


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class RelationshipState:
    familiarity: float = 0.35
    trust: float = 0.50
    playfulness: float = 0.35
    conversational_closeness: float = 0.25
    recent_dynamic: str = "neutral"

    def bounded(self) -> "RelationshipState":
        self.familiarity = clamp(self.familiarity)
        self.trust = clamp(self.trust)
        self.playfulness = clamp(self.playfulness)
        self.conversational_closeness = clamp(self.conversational_closeness)
        return self


@dataclass
class CharacterEmotionState:
    primary_emotion: str = "neutral"
    secondary_emotion: str | None = None
    intensity: float = 0.25
    arousal: str = "low"
    valence: str = "neutral"
    age: int = 0

    def bounded(self) -> "CharacterEmotionState":
        self.intensity = clamp(self.intensity)
        return self


@dataclass
class CharacterReaction:
    emotion: str = "neutral"
    attitude: str = "neutral"
    reaction: str = "none"
    motion_intent: str = "none"
    speaking_style_modifier: str = "normal"
    intensity: float = 0.25

    def bounded(self) -> "CharacterReaction":
        self.intensity = clamp(self.intensity)
        return self


@dataclass
class CharacterRuntimeState:
    relationship: RelationshipState = field(default_factory=RelationshipState)
    emotion: CharacterEmotionState = field(default_factory=CharacterEmotionState)
    reaction: CharacterReaction = field(default_factory=CharacterReaction)
    turn_count: int = 0
