import json
import logging
from inspect import signature

from app.agent.models import ChatMessage
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.exceptions import LLMRateLimitError
from app.llm.models import ToolRouteDecision
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolRouter:
    """Small capability selector; it never validates arguments or executes tools."""

    def __init__(self, provider: LLMProvider, registry: ToolRegistry, settings: Settings) -> None:
        self._provider = provider
        self._registry = registry
        self._settings = settings
        self.last_usage = None
        self.last_rate_limit = None
        self.last_finish_reason = None
        self.last_error: str | None = None
        self.last_prompt_chars = 0
        self.last_context_message_count = 0
        self.last_context_chars = 0

    async def route(self, message: str, context: list[ChatMessage] | None = None) -> ToolRouteDecision:
        hints = "\n".join(f"{item['name']}: {item['routing_hint']}" for item in self._registry.get_routing_hints())
        tool_names = [item["name"] for item in self._registry.get_routing_hints()]
        route_enum = ["NONE", *tool_names]
        response_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "tool_route_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"tool_name": {"type": "string", "enum": route_enum}},
                    "required": ["tool_name"],
                    "additionalProperties": False,
                },
            },
        }
        prompt = (
            "Classify whether the user's request requires one available tool.\n"
            "Select exactly one tool name or NONE. Choose semantic intent, not isolated words.\n"
            "If casual conversation needs no current external or system information, choose NONE.\n"
            "A reaction, opinion, complaint, or small talk about weather is still NONE unless the user asks for current or future weather information.\n"
            "Return only the structured routing decision. NONE means no tool.\n\n"
            f"Available capabilities:\n{hints}"
        )
        recent = context[-4:] if context else []
        context_text = "\n".join(f"{item.role}: {item.content}" for item in recent) or "(none)"
        classification = f"{prompt}\nRecent context:\n{context_text}\nCurrent request:\n{message}\nReturn only the structured routing decision."
        messages = [ChatMessage(role="system", content=classification)]
        self.last_prompt_chars = len(classification)
        self.last_context_message_count = len(recent)
        self.last_context_chars = sum(len(item.content) for item in recent)
        kwargs = {
            "response_format": response_schema,
            "model": self._settings.llm_router_model or self._settings.llm_model,
            "temperature": self._settings.llm_router_temperature,
            "max_completion_tokens": self._settings.llm_router_max_completion_tokens,
            "reasoning_effort": self._settings.llm_router_reasoning_effort or self._settings.llm_reasoning_effort,
            "reasoning_format": self._settings.llm_router_reasoning_format,
        }
        try:
            parameters = signature(self._provider.chat).parameters
            accepts_kwargs = any(item.kind == item.VAR_KEYWORD for item in parameters.values())
            if not accepts_kwargs and not all(name in parameters for name in kwargs):
                logger.warning("router_provider_unsupported")
                return ToolRouteDecision()
            response = await self._provider.chat(messages, **kwargs)
            self.last_usage = response.usage
            self.last_rate_limit = response.rate_limit
            self.last_finish_reason = response.finish_reason
            self.last_error = None
            logger.info(
                "llm_usage phase=router prompt_tokens=%s completion_tokens=%s total_tokens=%s remaining_tokens=%s reset_tokens=%s",
                getattr(response.usage, "prompt_tokens", None), getattr(response.usage, "completion_tokens", None),
                getattr(response.usage, "total_tokens", None), getattr(response.rate_limit, "remaining_tokens", None),
                getattr(response.rate_limit, "reset_tokens", None),
            )
            data = json.loads(response.content or "{}")
            decision = ToolRouteDecision.model_validate(data)
            if decision.tool_name == "NONE":
                return ToolRouteDecision()
            if decision.tool_name is not None and self._registry.get(decision.tool_name) is None:
                logger.warning("router_unknown_tool tool_name=%s", decision.tool_name)
                return ToolRouteDecision()
            return decision
        except LLMRateLimitError as exc:
            self.last_rate_limit = exc.rate_limit
            self.last_error = "rate_limited"
            logger.warning("router_rate_limited retry_after=%s remaining_tokens=%s reset_tokens=%s", getattr(exc.rate_limit, "retry_after", None), getattr(exc.rate_limit, "remaining_tokens", None), getattr(exc.rate_limit, "reset_tokens", None))
            return ToolRouteDecision()
        except Exception:
            self.last_error = "router_failed"
            logger.exception("router_failed")
            return ToolRouteDecision()
