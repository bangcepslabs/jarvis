from dataclasses import dataclass

from app.agent.models import PresentationHint
from app.character.context import build_character_context
from app.character.planner import apply_reaction, decay_emotion, plan_reaction
from app.character.profile import AvatarIdentity, CharacterProfile, DEFAULT_AVATAR_IDENTITY, DEFAULT_CHARACTER_PROFILE
from app.character.state import CharacterRuntimeState


@dataclass
class ConversationState:
    current_topic: str | None = None
    recent_user_intent: str | None = None
    last_assistant_action: str | None = None


class CharacterBrain:
    """Small in-memory character continuity layer, independent of authorization."""

    def __init__(self, profile: CharacterProfile = DEFAULT_CHARACTER_PROFILE, avatar_identity: AvatarIdentity = DEFAULT_AVATAR_IDENTITY) -> None:
        self.profile = profile
        self.avatar_identity = avatar_identity
        self._states: dict[str, ConversationState] = {}
        self._runtime_states: dict[str, CharacterRuntimeState] = {}

    def prepare(self, conversation_id: str, user_message: str) -> None:
        """Advance transient character state before the next LLM prompt."""
        runtime = self._runtime_states.setdefault(conversation_id, CharacterRuntimeState())
        decay_emotion(runtime)
        text = " ".join(user_message.casefold().split())
        if any(marker in text for marker in ("cpu", "gpu", "server", "api", "docker", "\uC11C\uBC84", "\uB85C\uADF8", "\uCF54\uB4DC")):
            dynamic = "technical"
        elif any(marker in text for marker in ("\u314B\u314B", "\u314E\u314E", "\uC7A5\uB09C", "\uB180\uB9AC", "\uBD80\uB044", "\uC57C\uD588", "\uC57C\uD55C", "\uC704\uD5D8")):
            dynamic = "teasing"
        elif any(marker in text for marker in ("\uC608\uC058", "\uADC0\uC5FD", "\uBA4B\uC9C0", "\uCE6D\uCC2C")):
            dynamic = "playful"
        elif any(marker in text for marker in ("\uD53C\uACE4", "\uC9C0\uCCD0", "\uD798\uB4E4", "\uC878\uB824")):
            dynamic = "supportive"
        else:
            dynamic = "casual_chat"
        apply_reaction(runtime, plan_reaction(user_message, runtime), dynamic)

    def context(self, conversation_id: str, available_tool_names: tuple[str, ...] = (), *, current_expression: str | None = None, current_motion: str | None = None) -> str:
        state = self._states.get(conversation_id, ConversationState())
        runtime = self._runtime_states.get(conversation_id, CharacterRuntimeState())
        relationship = runtime.relationship
        emotion = runtime.emotion
        reaction = runtime.reaction
        return build_character_context(
            self.profile,
            current_topic=state.current_topic,
            recent_user_intent=state.recent_user_intent,
            last_assistant_action=state.last_assistant_action,
            available_tool_names=available_tool_names,
            avatar_identity=self.avatar_identity,
            current_expression=current_expression,
            current_motion=current_motion,
            relationship_state=(
                f"familiarity={relationship.familiarity:.2f}, trust={relationship.trust:.2f}, "
                f"playfulness={relationship.playfulness:.2f}, closeness={relationship.conversational_closeness:.2f}, "
                f"recent_dynamic={relationship.recent_dynamic}"
            ),
            emotion_state=(
                f"primary={emotion.primary_emotion}, secondary={emotion.secondary_emotion or 'none'}, "
                f"intensity={emotion.intensity:.2f}, arousal={emotion.arousal}, valence={emotion.valence}"
            ),
            reaction_state=(
                f"emotion={reaction.emotion}, attitude={reaction.attitude}, reaction={reaction.reaction}, "
                f"motion_intent={reaction.motion_intent}, speaking_style={reaction.speaking_style_modifier}, "
                f"intensity={reaction.intensity:.2f}"
            ),
        )

    def presentation_hint(self, conversation_id: str) -> PresentationHint:
        """Adapt semantic reaction to the existing presentation contract."""
        reaction = self._runtime_states.get(conversation_id, CharacterRuntimeState()).reaction
        emotion = {
            "embarrassed": "playful",
            "shy": "playful",
            "amused": "playful",
            "focused": "thinking",
            "relaxed": "neutral",
        }.get(reaction.emotion, reaction.emotion)
        allowed_emotions = {"neutral", "happy", "excited", "surprised", "concerned", "thinking", "playful"}
        allowed_attitudes = {"neutral", "friendly", "playful", "supportive", "curious", "serious", "confident"}
        allowed_reactions = {"none", "acknowledge", "agree", "disagree", "celebrate", "surprise", "worry", "think", "tease", "encourage"}
        allowed_motion = {"none", "subtle", "positive", "reaction"}
        return PresentationHint(
            emotion=emotion if emotion in allowed_emotions else "neutral",
            intensity=reaction.intensity,
            motion_intent=reaction.motion_intent if reaction.motion_intent in allowed_motion else "none",
            attitude=reaction.attitude if reaction.attitude in allowed_attitudes else "neutral",
            reaction=reaction.reaction if reaction.reaction in allowed_reactions else "none",
            duration="short" if reaction.speaking_style_modifier in {"short_deflecting", "brief_appreciation"} else "normal",
        )

    def observe(self, conversation_id: str, user_message: str, response) -> None:
        state = self._states.setdefault(conversation_id, ConversationState())
        compact = " ".join(user_message.split())
        state.current_topic = compact[:120] or state.current_topic
        state.recent_user_intent = compact[:120] or "unknown"
        if response.tool_calls:
            state.last_assistant_action = response.tool_calls[-1].name
        elif response.pending_action:
            state.last_assistant_action = response.pending_action.tool_name
        else:
            state.last_assistant_action = "conversation"
        runtime = self._runtime_states.setdefault(conversation_id, CharacterRuntimeState())
        hint = getattr(response, "presentation_hint", None)
        if hint is not None and getattr(hint, "emotion", "neutral") != "neutral":
            runtime.emotion.primary_emotion = hint.emotion
            runtime.emotion.intensity = hint.intensity
            runtime.emotion.age = 0
