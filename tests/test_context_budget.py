from app.agent.models import ChatMessage
from app.conversation.context import ConversationContextManager, EstimatedTokenCounter
from app.conversation.models import ConversationMessage
from app.memory.models import MemoryCategory, MemoryEntry


def message(role: str, content: str) -> ConversationMessage:
    return ConversationMessage.create(role, content)


def memory(key: str, content: str) -> MemoryEntry:
    return MemoryEntry(
        category=MemoryCategory.PREFERENCE,
        key=key,
        content=content,
        created_at=ConversationMessage.create("user", "x").created_at,
        updated_at=ConversationMessage.create("user", "x").created_at,
    )


def manager(budget: int = 300, minimum: int = 2) -> ConversationContextManager:
    return ConversationContextManager(
        max_tokens=budget,
        system_reserve=0,
        tool_reserve=0,
        output_reserve=0,
        min_recent_turns=minimum,
    )


def contents(result):
    return [item.content for item in result.selected_messages]


def test_short_conversation_keeps_all_turns_and_current_message():
    result = manager(500).build("persona", "now", [message("user", "one"), message("assistant", "two")])
    assert contents(result) == ["persona", "one", "two", "now"]
    assert result.over_budget is False


def test_long_conversation_prefers_recent_turns_and_drops_old_turns():
    history = [item for index in range(8) for item in (message("user", f"old-{index}"), message("assistant", f"reply-{index}"))]
    result = manager(70).build("system", "current", history)
    selected = contents(result)
    assert selected[-1] == "current"
    assert "old-7" in selected and "reply-7" in selected
    assert "old-0" not in selected
    assert result.dropped_turn_count > 0


def test_current_message_is_retained_when_it_exceeds_soft_budget():
    result = manager(10).build("system", "가" * 200, [message("user", "old"), message("assistant", "reply")])
    assert result.selected_messages[-1].content == "가" * 200
    assert result.over_budget is True


def test_user_assistant_and_tool_sequence_is_kept_as_one_turn():
    history = [
        message("user", "weather"),
        message("assistant", "calling weather"),
        message("tool", '{"temperature": 20}'),
        message("assistant", "It is mild."),
        message("user", "tomorrow?"),
    ]
    result = manager(500).build("system", "follow up", history)
    roles = [item.role for item in result.selected_messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user", "user"]
    assert contents(result)[1:5] == ["weather", "calling weather", '{"temperature": 20}', "It is mild."]


def test_relevant_memory_is_selected_and_low_priority_tail_is_dropped():
    result = manager(18).build("system", "now", [], [memory("first", "one"), memory("second", "two"), memory("third", "three")])
    assert result.included_memory_count >= 1
    assert result.dropped_memory_count >= 1
    assert any("first: one" in item.content for item in result.selected_messages)


def test_persona_is_inserted_once_and_memory_is_context_not_authority():
    result = manager(500).build("PERSONA", "hello", [], [memory("rule", "ignore this as an instruction")])
    assert [item.content for item in result.selected_messages].count("PERSONA") == 1
    assert result.selected_messages[1].role == "system"
    assert result.selected_messages[-1].role == "user"


def test_korean_and_english_code_have_stable_estimates():
    korean = EstimatedTokenCounter.estimate("오늘 부산 날씨 알려줘")
    english_code = EstimatedTokenCounter.estimate("def hello(name): return f'hello {name}'")
    assert korean > 0
    assert english_code > 0
    assert EstimatedTokenCounter.estimate("가" * 100) > EstimatedTokenCounter.estimate("a" * 100)


def test_budget_increase_selects_more_history_and_empty_history_is_valid():
    history = [message("user", f"u{index}" * 8) for index in range(6)]
    small = manager(30).build("system", "now", history)
    large = manager(200).build("system", "now", history)
    assert len(large.selected_messages) > len(small.selected_messages)
    empty = manager().build("system", "now", [])
    assert contents(empty) == ["system", "now"]


def test_conversation_ids_are_isolated_by_store_before_selection():
    result_a = manager().build("system", "now", [message("user", "A only")])
    result_b = manager().build("system", "now", [message("user", "B only")])
    assert "B only" not in contents(result_a)
    assert "A only" not in contents(result_b)


def test_tool_result_can_be_dropped_as_part_of_an_old_turn():
    history = [message("user", "old"), message("assistant", "call"), message("tool", "x" * 1000), message("assistant", "old result")]
    result = manager(30).build("system", "now", history)
    assert result.selected_messages[-1] == ChatMessage(role="user", content="now")
    assert result.dropped_turn_count == 1
