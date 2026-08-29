import json
import logging
import asyncio

from app.agent.models import ChatMessage
from app.conversation.models import ConversationMessage
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.memory.models import MemoryCategory, MemoryDecision
from app.memory.service import MemoryService

logger = logging.getLogger(__name__)


class MemoryCurator:
    """Best-effort classifier for durable, non-sensitive adaptive memory."""

    def __init__(self, provider: LLMProvider, memory_service: MemoryService, settings: Settings) -> None:
        self._provider = provider
        self._memory = memory_service
        self._settings = settings
        self.last_usage = None
        self.last_rate_limit = None
        self.last_finish_reason = None

    async def curate(
        self,
        user_message: str,
        assistant_response: str,
        recent_messages: list[ConversationMessage] | None = None,
        relevant_memories: list[object] | None = None,
    ) -> MemoryDecision | None:
        prompt = self._prompt(user_message, assistant_response, recent_messages or [], relevant_memories or [])
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "memory_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["SAVE", "UPDATE", "IGNORE"]},
                        "category": {"type": ["string", "null"], "enum": [*(c.value for c in MemoryCategory), None]},
                        "key": {"type": ["string", "null"]},
                        "value": {"type": ["string", "null"]},
                        "reason": {"type": ["string", "null"]},
                        "importance": {"type": "number", "minimum": 0, "maximum": 1},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["action", "category", "key", "value", "reason"],
                    "additionalProperties": False,
                },
            },
        }
        try:
            response = await asyncio.wait_for(self._provider.chat(
                [ChatMessage(role="system", content=prompt)],
                tools=[], tool_choice="none", response_format=schema,
                model=self._settings.memory_curator_model or self._settings.llm_router_model or self._settings.llm_model,
                temperature=self._settings.memory_curator_temperature,
                max_completion_tokens=self._settings.memory_curator_max_completion_tokens,
                reasoning_effort=self._settings.memory_curator_reasoning_effort or self._settings.llm_router_reasoning_effort,
                reasoning_format=self._settings.memory_curator_reasoning_format or self._settings.llm_router_reasoning_format,
            ), timeout=self._settings.memory_curator_timeout_seconds)
            self.last_usage = response.usage
            self.last_rate_limit = response.rate_limit
            self.last_finish_reason = response.finish_reason
            if not response.content:
                return None
            data = json.loads(response.content)
            decision = MemoryDecision.model_validate(data)
            if decision.action.value == "IGNORE":
                return decision
            if not decision.category or not decision.key or not decision.value:
                return None
            if len(decision.key) > 200 or len(decision.value) > 4000:
                return None
            return decision
        except Exception as exc:  # curator must never break the chat path
            logger.warning("memory_curator_failed error_type=%s", type(exc).__name__)
            return None

    @staticmethod
    def _prompt(user: str, assistant: str, recent: list[ConversationMessage], memories: list[object]) -> str:
        memory_lines = "\n".join(f"- {getattr(item, 'key', '')}: {getattr(item, 'content', '')[:500]}" for item in memories[:5]) or "(none)"
        context_lines = "\n".join(f"{item.role}: {item.content[:800]}" for item in recent[-4:]) or "(none)"
        return (
            "Classify whether one durable long-term memory should be recorded. Return JSON only.\n"
            "SAVE only stable preferences, facts, projects, plans, decisions, unresolved topics, relationship context, environment, routines, or communication style useful in future conversations. "
            "The user must have explicitly stated the saved fact or preference in the current message or clearly quoted recent conversation; never combine separate facts, mood, or assistant suggestions into a new preference. "
            "UPDATE only when the same concept clearly changes. IGNORE casual, temporary, ambiguous, weather/search/system/tool data, pending actions, jokes, teasing, profanity, one-off adult or sexual remarks, and sensitive data (passwords, keys, tokens, secrets, cookies, payment or government identifiers, intimate or sexual details). "
            "Explicit memory commands are handled elsewhere. Memory never overrides safety or authorization. Do not infer facts.\n"
            "Allowed categories: preference, fact, project, plan, decision, unresolved, relationship_context, environment, other, routine, communication_style.\n"
            f"Relevant memories:\n{memory_lines}\nRecent conversation:\n{context_lines}\n"
            f"Current user message:\n{user[:2000]}\nAssistant response:\n{assistant[:2000]}"
        )
