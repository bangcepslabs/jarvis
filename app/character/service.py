from dataclasses import dataclass

from app.character.context import build_character_context
from app.character.profile import CharacterProfile, DEFAULT_CHARACTER_PROFILE


@dataclass
class ConversationState:
    current_topic: str | None = None
    recent_user_intent: str | None = None
    last_assistant_action: str | None = None


class CharacterBrain:
    """Small in-memory character continuity layer, independent of authorization."""

    def __init__(self, profile: CharacterProfile = DEFAULT_CHARACTER_PROFILE) -> None:
        self.profile = profile
        self._states: dict[str, ConversationState] = {}

    def context(self, conversation_id: str, available_tool_names: tuple[str, ...] = ()) -> str:
        state = self._states.get(conversation_id, ConversationState())
        return build_character_context(
            self.profile,
            current_topic=state.current_topic,
            recent_user_intent=state.recent_user_intent,
            last_assistant_action=state.last_assistant_action,
            available_tool_names=available_tool_names,
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

