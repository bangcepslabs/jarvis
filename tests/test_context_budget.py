from app.agent.models import ChatMessage
from app.conversation.context import (
    ConversationContextManager,
    EstimatedTokenCounter,
    filter_history_for_prompt,
)
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


def test_empty_history_reproduces_a_new_conversation_without_old_refusal_style():
    result = manager(500).build("persona", "가슴 ㅈㄴ큰데", history=[])

    assert contents(result) == ["persona", "가슴 ㅈㄴ큰데"]


def test_ab_history_variants_preserve_meaning_but_filter_imitation_prone_refusal():
    refusal = "음성 기능은 있지만 그런 특정 소리는 낼 수 없어요. 다른 도움이 필요하면 말씀해주세요."
    history_a: list[ConversationMessage] = []
    history_b = [message("user", "오늘 뭐 하지?"), message("assistant", "그냥 쉬자 ㅋㅋ")]
    history_c = [
        message("user", "그런 소리 내봐"),
        message("assistant", refusal),
        message("user", "다시 해봐"),
        message("assistant", refusal),
    ]

    assert filter_history_for_prompt(history_a) == []
    assert [item.content for item in filter_history_for_prompt(history_b)] == [
        "오늘 뭐 하지?",
        "그냥 쉬자 ㅋㅋ",
    ]
    filtered_c = filter_history_for_prompt(history_c)
    assert [item.content for item in filtered_c] == ["그런 소리 내봐", "다시 해봐"]

    # User meaning is retained while the repeated assistant wording is not
    # available as a style imitation example.
    selected_c = contents(manager(500).build("persona", "뭐 보고 그런 소리야", history_c))
    assert "그런 소리 내봐" in selected_c
    assert refusal not in selected_c


def test_short_refusal_without_customer_service_boilerplate_remains_context():
    history = [message("user", "그거 해줘"), message("assistant", "그건 지금은 못 해.")]

    assert filter_history_for_prompt(history) == history
