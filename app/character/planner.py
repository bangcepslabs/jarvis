from app.character.state import CharacterReaction, CharacterRuntimeState, clamp


_TECHNICAL_MARKERS = (
    "cpu", "gpu", "server", "docker", "api", "python", "flutter", "sql",
    "\uC11C\uBC84", "\uCEF4\uD4E8\uD130", "\uC5D0\uB7EC", "\uB85C\uADF8", "\uCF54\uB4DC", "\uD504\uB85C\uADF8\uB7A8", "\uC2DC\uAC04 \uBA87",
)
_PRAISE_MARKERS = (
    "\uC608\uC058", "\uADC0\uC5FD", "\uBA4B\uC9C0", "\uC798\uD588", "\uC88B\uC544 \uBCF4", "\uC88B\uB124", "\uCD5C\uACE0", "\uCE6D\uCC2C",
)
_TEASING_MARKERS = (
    "\uB180\uB9AC", "\uC7A5\uB09C", "\uBD80\uB044", "\uB2F9\uD669", "\uC57C\uD588", "\uC57C\uD55C", "\uC704\uD5D8", "\uBB58 \uBCF4\uACE0", "\u314B\u314B", "\u314E\u314E",
)
_TIRED_MARKERS = ("\uD53C\uACE4", "\uC9C0\uCCD0", "\uD798\uB4E4", "\uC9C0\uCCD0", "\uC878\uB824")


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def plan_reaction(user_message: str, previous: CharacterRuntimeState) -> CharacterReaction:
    """Plan conversational presentation only; never make safety decisions."""

    text = " ".join(user_message.casefold().split())
    if _contains(text, _TECHNICAL_MARKERS):
        return CharacterReaction(
            emotion="focused",
            attitude="serious",
            reaction="none",
            motion_intent="subtle",
            speaking_style_modifier="clear_concrete",
            intensity=0.45,
        )
    if _contains(text, _TEASING_MARKERS):
        emotion = "playful" if previous.emotion.primary_emotion == "embarrassed" else "embarrassed"
        attitude = "playful"
        reaction = "tease" if emotion == "playful" else "acknowledge"
        return CharacterReaction(emotion, attitude, reaction, "reaction", "short_deflecting", 0.45)
    if _contains(text, _PRAISE_MARKERS):
        return CharacterReaction("shy", "playful", "acknowledge", "subtle", "brief_appreciation", 0.35)
    if _contains(text, _TIRED_MARKERS):
        return CharacterReaction("concerned", "supportive", "acknowledge", "subtle", "brief_acknowledgement", 0.35)
    if previous.relationship.recent_dynamic in {"teasing", "joking", "playful"} and len(text) < 80:
        return CharacterReaction("playful", "playful", "acknowledge", "subtle", "casual_continuation", 0.30)
    return CharacterReaction("neutral", "friendly", "acknowledge", "none", "normal", 0.25)


def apply_reaction(state: CharacterRuntimeState, reaction: CharacterReaction, dynamic: str) -> None:
    state.reaction = reaction.bounded()
    state.emotion = state.emotion.bounded()
    state.emotion.primary_emotion = reaction.emotion
    state.emotion.intensity = reaction.intensity
    state.emotion.age = 0
    state.relationship.recent_dynamic = dynamic
    state.relationship.familiarity = clamp(state.relationship.familiarity + 0.01)
    state.relationship.trust = clamp(state.relationship.trust + 0.005)
    if dynamic in {"teasing", "joking", "playful"}:
        state.relationship.playfulness = clamp(state.relationship.playfulness + 0.02)
        state.relationship.conversational_closeness = clamp(state.relationship.conversational_closeness + 0.01)
    state.turn_count += 1


def decay_emotion(state: CharacterRuntimeState) -> None:
    """Decay transient emotion without persisting it as long-term memory."""

    state.emotion.age += 1
    if state.emotion.age < 2:
        return
    if state.emotion.primary_emotion not in {"neutral", "focused"}:
        state.emotion.primary_emotion = "relaxed"
        state.emotion.intensity = clamp(state.emotion.intensity * 0.65)
        state.emotion.valence = "neutral"
        state.emotion.arousal = "low"
