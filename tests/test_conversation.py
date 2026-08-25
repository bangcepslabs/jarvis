from app.agent.jarvis_agent import JarvisAgent
from app.conversation.models import ConversationMessage
from app.conversation.store import InMemoryConversationStore
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class RecordingProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[list[object]] = []

    async def chat(self, messages, tools=None):
        self.requests.append(messages)
        return LLMResponse(content="ok")


async def test_store_append_recent_clear_and_isolation():
    store = InMemoryConversationStore(max_messages=3)
    await store.append("a", ConversationMessage.create("user", "one"))
    await store.append("a", ConversationMessage.create("assistant", "two"))
    await store.append("a", ConversationMessage.create("user", "three"))
    await store.append("a", ConversationMessage.create("assistant", "four"))
    assert [m.content for m in await store.list_recent("a")] == ["two", "three", "four"]
    assert await store.count("b") == 0
    await store.clear("a")
    assert await store.count("a") == 0


async def test_agent_uses_recent_context_and_conversation_isolation():
    provider = RecordingProvider()
    store = InMemoryConversationStore()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), conversation_store=store, conversation_max_messages=4, conversation_max_context_chars=100)
    await agent.respond("first", "a")
    await agent.respond("follow up", "a")
    await agent.respond("other", "b")
    second = provider.requests[1]
    assert [m.content for m in second if getattr(m, "role", None) in ("user", "assistant")] == ["first", "ok", "follow up"]
    third = provider.requests[2]
    assert [m.content for m in third if getattr(m, "role", None) == "user"] == ["other"]


async def test_context_character_limit_is_applied():
    provider = RecordingProvider()
    store = InMemoryConversationStore()
    agent = JarvisAgent(provider, ToolExecutor(ToolRegistry()), conversation_store=store, conversation_max_context_chars=10)
    await agent.respond("123456789012345", "a")
    await agent.respond("next", "a")
    context = [m for m in provider.requests[1] if getattr(m, "role", None) in ("user", "assistant")]
    assert sum(len(m.content) for m in context) <= 10 + len("next")
