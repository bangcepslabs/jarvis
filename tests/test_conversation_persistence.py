import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest

from app.conversation.models import ConversationMessage
from app.conversation.store import SQLiteConversationStore
from app.conversation.summary import SQLiteConversationSummaryStore, conversation_turn_key


def message(role: str, content: str, second: int) -> ConversationMessage:
    return ConversationMessage(role, content, datetime(2026, 1, 1, tzinfo=UTC).replace(microsecond=second))


@pytest.mark.asyncio
async def test_conversation_history_survives_store_recreation_and_preserves_order(tmp_path):
    path = str(tmp_path / "jarvis.db")
    first = SQLiteConversationStore(path)
    await first.append("a", message("user", "one", 1))
    await first.append("a", message("assistant", "two", 2))
    await first.append("a", message("tool", "three", 3))

    second = SQLiteConversationStore(path)
    assert [item.content for item in await second.list_recent("a")] == ["one", "two", "three"]
    assert [item.content for item in await second.list_recent("a", 2)] == ["two", "three"]
    assert await second.count("a") == 3


@pytest.mark.asyncio
async def test_conversations_are_isolated_and_clear_removes_only_one(tmp_path):
    path = str(tmp_path / "jarvis.db")
    store = SQLiteConversationStore(path)
    await store.append("a", message("user", "a-only", 1))
    await store.append("b", message("user", "b-only", 2))
    assert [item.content for item in await store.list_recent("a")] == ["a-only"]
    assert [item.content for item in await store.list_recent("b")] == ["b-only"]
    await store.clear("a")
    assert await store.count("a") == 0
    assert await store.count("b") == 1


@pytest.mark.asyncio
async def test_concurrent_appends_keep_unique_deterministic_sequences(tmp_path):
    store = SQLiteConversationStore(str(tmp_path / "jarvis.db"))
    await asyncio.gather(*(store.append("a", message("user", f"message-{index}", index + 1)) for index in range(20)))
    messages = await store.list_recent("a")
    assert len(messages) == 20
    assert {item.content for item in messages} == {f"message-{index}" for index in range(20)}


def test_summary_survives_store_recreation_and_persists_cursor(tmp_path):
    path = str(tmp_path / "jarvis.db")
    conversation = SQLiteConversationStore(path)
    turn = [message("user", "old question", 1), message("assistant", "old answer", 2)]
    asyncio.run(conversation.append("a", turn[0]))
    asyncio.run(conversation.append("a", turn[1]))
    key = conversation_turn_key(turn)
    SQLiteConversationSummaryStore(path).save("a", "compact context", {key})

    state = SQLiteConversationSummaryStore(path).get("a")
    assert state is not None
    assert state.text == "compact context"
    assert key in state.summarized_keys
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT summarized_through_sequence FROM conversations WHERE id = 'a'").fetchone()[0] == 2


def test_malformed_rows_are_ignored_without_affecting_valid_history(tmp_path):
    path = str(tmp_path / "jarvis.db")
    store = SQLiteConversationStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO conversations(id, created_at, updated_at) VALUES ('a', 'now', 'now')")
        connection.execute("INSERT INTO conversation_messages(conversation_id, sequence, role, content, created_at) VALUES ('a', 1, 'unknown', 'bad', 'now')")
        connection.execute("INSERT INTO conversation_messages(conversation_id, sequence, role, content, created_at) VALUES ('a', 2, 'user', 'good', '2026-01-01T00:00:00+00:00')")
    assert [item.content for item in asyncio.run(store.list_recent("a"))] == ["good"]
