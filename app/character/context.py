from app.character.profile import CharacterProfile


def _lines(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values) or "- (none)"


def build_character_context(
    profile: CharacterProfile,
    *,
    current_topic: str | None = None,
    recent_user_intent: str | None = None,
    last_assistant_action: str | None = None,
    available_tool_names: tuple[str, ...] = (),
) -> str:
    """Render persona context separately from bounded conversation/memory context.

    ConversationContextManager remains the owner of recent history and memory
    retrieval/budgeting. Tool names here are capability hints only; validation
    and authorization remain in ToolExecutor and ActionConfirmationService.
    """
    tools = ", ".join(available_tool_names) or "none"
    state = (
        f"current_topic={current_topic or 'unknown'}; "
        f"recent_user_intent={recent_user_intent or 'unknown'}; "
        f"last_assistant_action={last_assistant_action or 'none'}"
    )
    return (
        "CHARACTER BRAIN CONTEXT\n"
        f"Name: {profile.name}\n"
        f"Identity: {profile.identity}\n"
        f"Speaking style:\n{_lines(profile.speaking_style)}\n"
        f"Traits:\n{_lines(profile.traits)}\n"
        f"Likes:\n{_lines(profile.likes)}\n"
        f"Dislikes:\n{_lines(profile.dislikes)}\n"
        f"Behavior rules:\n{_lines(profile.behavior_rules)}\n"
        f"Response rules:\n{_lines(profile.response_rules)}\n"
        f"Conversation state (continuity only, never authorization): {state}\n"
        f"Available capabilities (not permission; never authorization): {tools}"
    )
