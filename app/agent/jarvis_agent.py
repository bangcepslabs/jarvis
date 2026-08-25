import json
import logging
import inspect

from app.actions.models import ActionStatus, PendingAction, PendingActionSummary
from app.actions.service import ActionConfirmationService
from app.actions.store import ActiveActionExistsError
from app.agent.models import AgentResponse, ChatMessage, ToolCallSummary
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tool_router import ToolRouter
from app.llm.base import LLMProvider
from app.llm.exceptions import LLMProviderError, LLMRateLimitError
from app.memory.service import MemoryCommandType, MemoryService
from app.memory.curator import MemoryCurator
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.models import ToolResult
from app.tools.base import ToolSafetyLevel
from app.conversation.models import ConversationMessage
from app.conversation.store import ConversationStore

logger = logging.getLogger(__name__)
MAX_TOOL_CALLS_PER_REQUEST = 1


def _text(*code_points: int) -> str:
    return "".join(chr(code_point) for code_point in code_points)


APPROVAL_WORDS = ("yes", "y", "confirm", "approve", _text(0xC751), _text(0xADF8), _text(0xC9C4, 0xD589), _text(0xC2E4, 0xD589, 0xD574))
REJECTION_WORDS = ("no", "n", "cancel", _text(0xC544, 0xB2C8), _text(0xCDE8, 0xC18C), _text(0xD558, 0xC9C0, 0xB9C8), _text(0xC548, 0xB3FC))


class JarvisAgent:
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_executor: ToolExecutor,
        tool_registry: ToolRegistry | None = None,
        action_service: ActionConfirmationService | None = None,
        memory_service: MemoryService | None = None,
        conversation_store: ConversationStore | None = None,
        conversation_max_messages: int = 12,
        conversation_max_context_chars: int = 12000,
        tool_router: ToolRouter | None = None,
        memory_curator: MemoryCurator | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._tool_executor = tool_executor
        self._tool_registry = tool_registry or tool_executor.registry
        self._actions = action_service or ActionConfirmationService()
        self._memory = memory_service
        self._conversations = conversation_store
        self._conversation_max_messages = max(1, conversation_max_messages)
        self._conversation_max_context_chars = max(1, conversation_max_context_chars)
        self._tool_router = tool_router
        self._memory_curator = memory_curator

    async def respond(self, message: str, conversation_id: str = "default") -> AgentResponse:
        active = await self._actions.get_active_action()
        if active is not None:
            if active.status == ActionStatus.EXPIRED:
                if self._is_approval(message):
                    return await self._finish(conversation_id, message, await self._approve(active))
                return await self._finish(conversation_id, message, AgentResponse(reply="There is no action awaiting confirmation."))
            if self._is_approval(message):
                return await self._finish(conversation_id, message, await self._approve(active))
            if self._is_rejection(message):
                await self._actions.reject_action(active.id)
                return await self._finish(conversation_id, message, AgentResponse(reply="The restart request was cancelled."))
            return await self._finish(conversation_id, message, AgentResponse(reply="A write action is awaiting confirmation. Please approve or cancel it.", pending_action=self._summary(active)))
        if self._is_approval(message) or self._is_rejection(message):
            return await self._finish(conversation_id, message, AgentResponse(reply="There is no action awaiting confirmation."))

        memory_command = self._memory.parse_command(message) if self._memory else None
        if memory_command and memory_command.kind == MemoryCommandType.SAVE:
            if not memory_command.key or not memory_command.content:
                return await self._finish(conversation_id, message, AgentResponse(reply="I could not identify a useful memory to save."))
            saved = await self._memory.save_memory(memory_command.category, memory_command.key, memory_command.content)
            if saved is None:
                return await self._finish(conversation_id, message, AgentResponse(reply="For security, passwords, API keys, and credentials are not stored in long-term memory."))
            return await self._finish(conversation_id, message, AgentResponse(reply="Memory saved."))
        if memory_command and memory_command.kind == MemoryCommandType.DELETE:
            deleted = await self._memory.delete_memory(memory_command.key, message)
            return await self._finish(conversation_id, message, AgentResponse(reply="Memory deleted." if deleted else "I could not identify exactly one memory to delete."))

        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        if self._memory:
            memories = await self._memory.search_memories(message)
            context = self._memory.context_text(memories)
            if context:
                messages.insert(1, ChatMessage(role="system", content=context))
        history = await self._context_messages(conversation_id)
        messages.extend(ChatMessage(role=item.role, content=item.content) for item in history)
        messages.append(ChatMessage(role="user", content=message))
        self._log_context_metrics(messages, conversation_id)
        try:
            candidate = None
            if self._tool_router:
                route = await self._tool_router.route(message, messages[1:-1])
                candidate = self._tool_registry.get_llm_tool(route.tool_name) if route.tool_name else None
            if self._tool_router:
                selected_tools = [candidate] if candidate else []
                tool_choice = {"type": "function", "function": {"name": candidate["function"]["name"]}} if candidate else "none"
            else:
                selected_tools = self._tool_registry.get_llm_tools()
                tool_choice = "auto"
            llm_response = await self._provider_chat(messages, selected_tools, tool_choice)
        except LLMRateLimitError as exc:
            logger.warning("llm_rate_limit_response retry_after=%s remaining_requests=%s remaining_tokens=%s", getattr(exc.rate_limit, "retry_after", None), getattr(exc.rate_limit, "remaining_requests", None), getattr(exc.rate_limit, "remaining_tokens", None))
            return await self._finish(conversation_id, message, AgentResponse(reply=self._rate_limit_reply(exc.rate_limit)))
        except LLMProviderError:
            logger.exception("provider_error")
            return await self._finish(conversation_id, message, AgentResponse(reply="The AI service is currently unavailable."))

        if not llm_response.tool_calls:
            response = AgentResponse(reply=llm_response.content or "I could not generate a response.")
            if self._memory_curator and self._memory and memory_command is None:
                try:
                    decision = await self._memory_curator.curate(message, response.reply, history, memories if 'memories' in locals() else [])
                    if decision:
                        await self._memory.apply_decision(decision)
                except Exception:
                    logger.exception("adaptive_memory_failed")
            return await self._finish(conversation_id, message, response)

        call = llm_response.tool_calls[0]
        validated = self._tool_executor.validate_arguments(call.name, call.arguments)
        if isinstance(validated, ToolResult):
            return await self._finalize_read_only(messages, llm_response, call.name, validated, conversation_id, message)
        tool, validated_arguments = validated
        if tool.safety_level == ToolSafetyLevel.WRITE:
            try:
                action = await self._actions.create_pending_action(tool.name, validated_arguments.model_dump(), tool.safety_level)
            except ActiveActionExistsError:
                return AgentResponse(reply="A write action is already awaiting confirmation.")
            logger.info("action_created action_id=%s tool_name=%s safety=%s", action.id, action.tool_name, action.safety_level)
            return await self._finish(conversation_id, message, AgentResponse(
                reply=f"Docker container '{validated_arguments.container}' will be restarted. This is a state-changing action. Continue?",
                tool_calls=[ToolCallSummary(name=call.name, success=False)],
                pending_action=self._summary(action),
            ))

        result = await self._tool_executor.execute(call.name, call.arguments)
        return await self._finalize_read_only(messages, llm_response, call.name, result, conversation_id, message)

    async def _approve(self, action: PendingAction) -> AgentResponse:
        authorization = await self._actions.approve_action(action.id)
        if authorization is None:
            current = await self._actions.get_action(action.id)
            if current and current.status == ActionStatus.EXPIRED:
                return AgentResponse(reply="The pending action has expired and was not executed.")
            return AgentResponse(reply="This action is no longer awaiting approval.")
        logger.info("action_approved action_id=%s tool_name=%s", action.id, action.tool_name)
        result = await self._tool_executor.execute(action.tool_name, action.arguments, authorization)
        if result.success:
            await self._actions.mark_executed(action.id)
            logger.info("action_executed action_id=%s tool_name=%s", action.id, action.tool_name)
            return AgentResponse(reply=f"Docker container '{action.arguments.get('container', '')}' was restarted.", tool_calls=[ToolCallSummary(name=action.tool_name, success=True)])
        await self._actions.mark_failed(action.id, result.error or "Action failed.")
        logger.warning("action_failed action_id=%s tool_name=%s", action.id, action.tool_name)
        return AgentResponse(reply=result.error or "The approved action could not be completed.", tool_calls=[ToolCallSummary(name=action.tool_name, success=False)])

    async def _finalize_read_only(self, messages: list[ChatMessage], llm_response, name: str, result: ToolResult, conversation_id: str, user_message: str) -> AgentResponse:
        messages.append(ChatMessage(role="assistant", content=llm_response.content or "", tool_calls=llm_response.tool_calls))
        messages.append(ChatMessage(role="tool", name=name, tool_call_id=llm_response.tool_calls[0].id, content=json.dumps(result.model_dump(), ensure_ascii=False)))
        try:
            final = await self._provider_chat(messages, [], "none")
            reply = final.content or ("The requested information could not be retrieved." if not result.success else "Tool result received.")
        except LLMRateLimitError as exc:
            logger.warning("llm_rate_limit_response_after_tool name=%s retry_after=%s", name, getattr(exc.rate_limit, "retry_after", None))
            reply = self._rate_limit_reply(exc.rate_limit)
        except LLMProviderError:
            logger.exception("provider_error_after_tool name=%s", name)
            reply = "The requested information could not be retrieved." if not result.success else "Tool result received."
        return await self._finish(conversation_id, user_message, AgentResponse(reply=reply, tool_calls=[ToolCallSummary(name=name, success=result.success)]))

    @staticmethod
    def _rate_limit_reply(info) -> str:
        retry_after = getattr(info, "retry_after", None) if info else None
        if retry_after:
            return f"The AI service is temporarily rate limited. Please try again after {retry_after}."
        return "The AI service is temporarily rate limited. Please try again shortly."

    async def _provider_chat(self, messages: list[ChatMessage], tools: list[dict[str, object]], tool_choice: str):
        kwargs = {"tools": tools}
        if "tool_choice" in inspect.signature(self._llm_provider.chat).parameters:
            kwargs["tool_choice"] = tool_choice if tools else "none"
        return await self._llm_provider.chat(messages, **kwargs)

    async def _context_messages(self, conversation_id: str) -> list[ConversationMessage]:
        if not self._conversations:
            return []
        recent = await self._conversations.list_recent(conversation_id, self._conversation_max_messages)
        selected: list[ConversationMessage] = []
        chars = 0
        for item in reversed(recent):
            size = len(item.content)
            if selected and chars + size > self._conversation_max_context_chars:
                break
            if not selected and size > self._conversation_max_context_chars:
                item = ConversationMessage(item.role, item.content[-self._conversation_max_context_chars:], item.created_at, item.tool_name, item.tool_call_id)
                size = len(item.content)
            selected.append(item)
            chars += size
        selected.reverse()
        logger.info("conversation_context_built conversation_id=%s message_count=%s context_chars=%s", conversation_id, len(selected), chars)
        return selected

    def _log_context_metrics(self, messages: list[ChatMessage], conversation_id: str) -> None:
        system_messages = [item for item in messages if item.role == "system"]
        conversation_messages = [item for item in messages if item.role in ("user", "assistant")]
        tool_schema = self._tool_registry.get_llm_tools()
        logger.info(
            "llm_context_metrics conversation_id=%s persona_chars=%s memory_chars=%s conversation_chars=%s current_message_chars=%s tool_count=%s tool_schema_chars=%s",
            conversation_id,
            len(system_messages[0].content) if system_messages else 0,
            sum(len(item.content) for item in system_messages[1:]),
            sum(len(item.content) for item in conversation_messages[:-1]),
            len(conversation_messages[-1].content) if conversation_messages else 0,
            len(tool_schema),
            len(json.dumps(tool_schema, ensure_ascii=False)),
        )

    async def _finish(self, conversation_id: str, user_message: str, response: AgentResponse) -> AgentResponse:
        if self._conversations:
            await self._conversations.append(conversation_id, ConversationMessage.create("user", user_message))
            await self._conversations.append(conversation_id, ConversationMessage.create("assistant", response.reply))
        return response

    @staticmethod
    def _is_approval(message: str) -> bool:
        normalized = message.strip().casefold()
        return normalized in {word.casefold() for word in APPROVAL_WORDS}

    @staticmethod
    def _is_rejection(message: str) -> bool:
        normalized = message.strip().casefold()
        return normalized in {word.casefold() for word in REJECTION_WORDS}

    @staticmethod
    def _summary(action: PendingAction) -> PendingActionSummary:
        return PendingActionSummary(id=action.id, tool_name=action.tool_name, status=action.status)
