import pytest

from app.agent.jarvis_agent import JarvisAgent
from app.conversation.context import filter_history_for_prompt
from app.conversation.models import ConversationMessage
from app.conversation.store import InMemoryConversationStore
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


FAILURE = "\uc751\ub2f5\uc744 \ub9cc\ub4e4\uc9c0 \ubabb\ud588\uc5b4\uc694. \ub2e4\uc2dc \ub9d0\uc500\ud574 \uc8fc\uc138\uc694."


class SequencedProvider(LLMProvider):
    def __init__(self, replies: list[str]) -> None:
        self._replies = iter(replies)
        self.requests = []

    async def chat(self, messages, tools=None, tool_choice=None, **kwargs):
        self.requests.append(messages)
        return LLMResponse(content=next(self._replies))


def message(role: str, content: str) -> ConversationMessage:
    return ConversationMessage.create(role, content)


def test_legacy_synthetic_failure_turns_are_removed_as_complete_pairs():
    poisoned = [
        item
        for index in range(5)
        for item in (message("user", f"question {index}"), message("assistant", FAILURE))
    ]
    direct_user_phrase = message("user", FAILURE)
    valid_reply = message("assistant", "\uc54c\uaca0\uc5b4. \ubb50 \ub3c4\uc640\uc904\uae4c?")

    filtered = filter_history_for_prompt([*poisoned, direct_user_phrase, valid_reply])

    assert [item.content for item in filtered] == [FAILURE, valid_reply.content]
    assert all(item.content != "question 0" for item in filtered)


@pytest.mark.asyncio
async def test_main_llm_prompt_omits_legacy_synthetic_failure_examples():
    provider = SequencedProvider(["\uc751, \uc9c0\uae08 \ub300\uae30 \uc911\uc774\uc57c."])
    store = InMemoryConversationStore()
    for index in range(5):
        await store.append("legacy", message("user", f"old question {index}"))
        await store.append("legacy", message("assistant", FAILURE))
    agent = JarvisAgent(
        provider,
        ToolExecutor(ToolRegistry()),
        conversation_store=store,
        conversation_max_messages=20,
    )

    await agent.respond("\uc9c0\uae08 \ubb50\ud574?", "legacy")

    prompt_contents = [item.content for item in provider.requests[0]]
    assert FAILURE not in prompt_contents
    assert all(not item.startswith("old question") for item in prompt_contents)


@pytest.mark.asyncio
async def test_generated_known_failure_is_retried_and_valid_reply_is_persisted():
    provider = SequencedProvider([FAILURE, "\uc9c0\uae08 \ub300\uae30 \uc911\uc774\uc57c."])
    store = InMemoryConversationStore()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), conversation_store=store)

    response = await agent.respond("\uc9c0\uae08 \ubb50\ud574?", "retry")

    assert response.reply == "\uc9c0\uae08 \ub300\uae30 \uc911\uc774\uc57c."
    assert response.response_origin == "llm_retry"
    assert len(provider.requests) == 2
    assert [item.content for item in await store.list_recent("retry")] == ["\uc9c0\uae08 \ubb50\ud574?", response.reply]


@pytest.mark.asyncio
async def test_repeated_generated_failure_uses_non_persistent_casual_fallback():
    provider = SequencedProvider([FAILURE, FAILURE])
    store = InMemoryConversationStore()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), conversation_store=store)

    response = await agent.respond("\uc9c0\uae08 \ubb50\ud574?", "fallback")

    assert response.response_origin == "synthetic_failure"
    assert response.persist_history is False
    assert response.reply == "\uc751\ub2f5\uc774 \ube44\uc5c8\uc5b4. \ud55c \ubc88\ub9cc \ub354 \ub9d0\ud574\uc918."
    assert await store.list_recent("fallback") == []
