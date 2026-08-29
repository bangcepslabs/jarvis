import json
import logging
import inspect
import re

from app.actions.models import ActionStatus, PendingAction, PendingActionSummary
from app.actions.service import ActionConfirmationService
from app.actions.store import ActiveActionExistsError
from app.agent.models import AgentResponse, ChatMessage, ToolCallSummary
from app.agent.prompt import build_system_prompt, infer_conversation_style
from app.agent.presentation import parse_presentation_response
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
from app.conversation.context import ConversationContextManager, ContextSelectionResult, EstimatedTokenCounter
from app.conversation.summary import ConversationSummarizer, ConversationSummaryStore, conversation_turn_key
from app.llm.calibration import LLMCalibrationCollector
from app.character.service import CharacterBrain

logger = logging.getLogger(__name__)
MAX_TOOL_CALLS_PER_REQUEST = 1


def _trace_response(stage: str, text: str | None) -> None:
    """Expose response provenance only at DEBUG; never emit it at INFO."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("response_trace stage=%s text=%r", stage, text or "")


def _text(*code_points: int) -> str:
    return "".join(chr(code_point) for code_point in code_points)


APPROVAL_WORDS = ("yes", "y", "confirm", "approve", _text(0xC751), _text(0xADF8), _text(0xC9C4, 0xD589), _text(0xC2E4, 0xD589, 0xD574))
REJECTION_WORDS = ("no", "n", "cancel", _text(0xC544, 0xB2C8), _text(0xCDE8, 0xC18C), _text(0xD558, 0xC9C0, 0xB9C8), _text(0xC548, 0xB3FC))


def _language_safe_reply(user_message: str, reply: str) -> str:
    """Keep fixed fallback replies in the language used by a Korean user."""
    if not re.search(r"[\uac00-\ud7a3]", user_message):
        return reply
    casual_fixed = {
        "The requested information could not be retrieved.": "\uc694\uccad\ud55c \uc815\ubcf4\ub97c \ubabb \uac00져왔\uc5b4.",
        "Tool result received.": "\ub3c4\uad6c \uacb0\uacfc \ub098\uc654\uc5b4.",
        "This action is no longer awaiting approval.": "\uc774 \uc791\uc5c5\uc740 \ub354 \uc774\uc0c1 \uc2b9\uc778 \ub300\uae30 \uc911\uc774 \uc544\ub2c8\uc57c.",
        "The pending action has expired and was not executed.": "\uc2b9\uc778 \uc2dc\uac04\uc774 \uc9c0\ub098\uc11c \uc2e4\ud589\ud558\uc9c0 \uc54a\uc558\uc5b4.",
        "The approved action could not be completed.": "\uc2b9\uc778\ub41c \uc791\uc5c5\uc744 \ub05d\ub0b4\uc9c0 \ubabb\ud588\uc5b4.",
    }
    if reply in casual_fixed:
        return casual_fixed[reply]
    return {
        "The AI service is currently unavailable.": "현재 AI 서비스를 사용할 수 없어요.",
        "I could not generate a response.": "응답을 만들지 못했어요. 다시 말씀해 주세요.",
        "The requested information could not be retrieved.": "요청한 정보를 가져오지 못했어요.",
        "Tool result received.": "도구 결과를 확인했어요.",
    }.get(reply, reply)


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
        context_manager: ConversationContextManager | None = None,
        summary_store: ConversationSummaryStore | None = None,
        summarizer: ConversationSummarizer | None = None,
        summary_enabled: bool = False,
        summary_min_new_turns: int = 4,
        calibration: LLMCalibrationCollector | None = None,
        character_brain: CharacterBrain | None = None,
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
        self._context_manager = context_manager or ConversationContextManager()
        self._context_manager_explicit = context_manager is not None
        self._summary_store = summary_store or ConversationSummaryStore()
        self._summarizer = summarizer
        self._summary_enabled = summary_enabled and summarizer is not None
        self._summary_min_new_turns = max(1, summary_min_new_turns)
        self._calibration = calibration or LLMCalibrationCollector()
        self._character_brain = character_brain or CharacterBrain()

    async def respond(self, message: str, conversation_id: str = "default", response_mode: str | None = None) -> AgentResponse:
        active = await self._actions.get_active_action()
        if active is not None:
            if active.status == ActionStatus.EXPIRED:
                if self._is_approval(message):
                    return await self._finish(conversation_id, message, await self._approve(active, message))
                return await self._finish(conversation_id, message, AgentResponse(reply="There is no action awaiting confirmation."))
            if self._is_approval(message):
                return await self._finish(conversation_id, message, await self._approve(active, message))
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

        memories = []
        if self._memory:
            memories = await self._memory.search_memories(message)
        history = await self._context_messages(conversation_id, all_history=self._context_manager_explicit)
        system_prompt = build_system_prompt(response_mode, infer_conversation_style(history)) + "\n\n" + self._character_brain.context(
            conversation_id,
            tuple(tool.name for tool in self._tool_registry.list_tools()),
        )
        summary_state = self._summary_store.get(conversation_id) if self._summary_enabled else None
        summary_update = None
        selection = self._context_manager.build(
            system_prompt,
            message,
            history,
            memories,
            summary=summary_state.text if summary_state else None,
        )
        if self._summary_enabled and self._summarizer:
            summarized_keys = summary_state.summarized_keys if summary_state else frozenset()
            new_dropped = [
                turn for turn in selection.dropped_turns
                if conversation_turn_key(turn) not in summarized_keys
            ]
            if len(new_dropped) >= self._summary_min_new_turns:
                update = await self._summarizer.update(
                    summary_state.text if summary_state else None,
                    new_dropped,
                )
                summary_update = update
                if update.updated and update.text:
                    summarized_keys = set(summarized_keys)
                    summarized_keys.update(conversation_turn_key(turn) for turn in new_dropped)
                    summary_state = self._summary_store.save(conversation_id, update.text, summarized_keys)
                    selection = self._context_manager.build(
                        system_prompt,
                        message,
                        history,
                        memories,
                        summary=summary_state.text,
                    )
        logger.info(
            "conversation_summary_metrics conversation_id=%s summary_present=%s "
            "summary_estimated_tokens=%s summary_updated=%s newly_summarized_turns=%s "
            "summary_update_failed=%s",
            conversation_id,
            bool(summary_state and summary_state.text),
            EstimatedTokenCounter.estimate(summary_state.text, "system") if summary_state else 0,
            bool(summary_update and summary_update.updated),
            summary_update.new_turn_count if summary_update else 0,
            bool(summary_update and summary_update.failed),
        )
        messages = selection.selected_messages
        self._log_context_metrics(messages, conversation_id, selection)
        try:
            candidate = None
            if self._tool_router:
                route = await self._tool_router.route(message, messages[1:-1])
                candidate = self._tool_registry.get_llm_tool(route.tool_name) if route.tool_name else None
            if self._tool_router:
                selected_tools = [candidate] if candidate else []
                # The router narrows the available tool set to one candidate.
                # Let the model emit a valid call instead of forcing a tool
                # call that Groq may reject as tool_use_failed.
                tool_choice = "auto" if candidate else "none"
            else:
                selected_tools = self._tool_registry.get_llm_tools()
                tool_choice = "auto"
            llm_response = await self._provider_chat(
                messages,
                selected_tools,
                tool_choice,
                summary_present=bool(summary_state and summary_state.text),
                conversation_turns=selection.selected_history_turns,
                memory_count=selection.included_memory_count,
                phase="main",
            )
        except LLMRateLimitError as exc:
            logger.warning("llm_rate_limit_response retry_after=%s remaining_requests=%s remaining_tokens=%s", getattr(exc.rate_limit, "retry_after", None), getattr(exc.rate_limit, "remaining_requests", None), getattr(exc.rate_limit, "remaining_tokens", None))
            return await self._finish(conversation_id, message, AgentResponse(reply=_language_safe_reply(message, self._rate_limit_reply(exc.rate_limit))))
        except LLMProviderError:
            logger.exception("provider_error")
            return await self._finish(conversation_id, message, AgentResponse(reply=_language_safe_reply(message, "The AI service is currently unavailable.")))

        if not llm_response.tool_calls:
            _trace_response("post_character_input", llm_response.content)
            reply, hint = parse_presentation_response(llm_response.content)
            response = AgentResponse(reply=_language_safe_reply(message, reply or "I could not generate a response."), presentation_hint=hint)
            if self._memory_curator and self._memory and memory_command is None:
                try:
                    decision = await self._memory_curator.curate(message, response.reply, history, memories)
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
            pending_reply = (
                "이건 실제로 변경되는 작업이라 확인이 필요해. 실행할까?"
                if re.search(r"[\uac00-\ud7a3]", message)
                else f"Docker container '{validated_arguments.container}' will be restarted. This changes state. Continue?"
            )
            return await self._finish(conversation_id, message, AgentResponse(
                reply=pending_reply,
                tool_calls=[ToolCallSummary(name=call.name, success=False)],
                pending_action=self._summary(action),
            ))

        result = await self._tool_executor.execute(call.name, call.arguments)
        return await self._finalize_read_only(messages, llm_response, call.name, result, conversation_id, message)

    async def _approve(self, action: PendingAction, user_message: str = "") -> AgentResponse:
        authorization = await self._actions.approve_action(action.id)
        if authorization is None:
            current = await self._actions.get_action(action.id)
            if current and current.status == ActionStatus.EXPIRED:
                return AgentResponse(reply=_language_safe_reply(user_message, "The pending action has expired and was not executed."))
            return AgentResponse(reply=_language_safe_reply(user_message, "This action is no longer awaiting approval."))
        logger.info("action_approved action_id=%s tool_name=%s", action.id, action.tool_name)
        result = await self._tool_executor.execute(action.tool_name, action.arguments, authorization)
        if result.success:
            await self._actions.mark_executed(action.id)
            logger.info("action_executed action_id=%s tool_name=%s", action.id, action.tool_name)
            completed = f"Docker container '{action.arguments.get('container', '')}' was restarted."
            return AgentResponse(reply=_language_safe_reply(user_message, completed), tool_calls=[ToolCallSummary(name=action.tool_name, success=True)])
        await self._actions.mark_failed(action.id, result.error or "Action failed.")
        logger.warning("action_failed action_id=%s tool_name=%s", action.id, action.tool_name)
        return AgentResponse(reply=_language_safe_reply(user_message, result.error or "The approved action could not be completed."), tool_calls=[ToolCallSummary(name=action.tool_name, success=False)])

    async def _finalize_read_only(self, messages: list[ChatMessage], llm_response, name: str, result: ToolResult, conversation_id: str, user_message: str) -> AgentResponse:
        messages.append(ChatMessage(role="assistant", content=llm_response.content or "", tool_calls=llm_response.tool_calls))
        messages.insert(1, ChatMessage(
            role="system",
            content=(
                "TOOL RESULT PRESENTATION\n"
                "Use the verified tool data to answer the user's question in the existing JARVIS character style. "
                "Keep the user's language and casual/formal tone consistent with the character context, including after a tool call. "
                "Preserve factual values exactly; do not invent health/status judgments or expose raw JSON. "
                "For a short everyday question, answer briefly."
            ),
        ))
        messages.append(ChatMessage(role="tool", name=name, tool_call_id=llm_response.tool_calls[0].id, content=json.dumps(result.model_dump(), ensure_ascii=False)))
        try:
            final = await self._provider_chat(messages, [], "none", phase="tool_final")
            _trace_response("post_character_input", final.content)
            reply, hint = parse_presentation_response(final.content)
            reply = reply or ("The requested information could not be retrieved." if not result.success else "Tool result received.")
        except LLMRateLimitError as exc:
            logger.warning("llm_rate_limit_response_after_tool name=%s retry_after=%s", name, getattr(exc.rate_limit, "retry_after", None))
            reply, hint = _language_safe_reply(user_message, self._rate_limit_reply(exc.rate_limit)), None
        except LLMProviderError:
            logger.exception("provider_error_after_tool name=%s", name)
            fallback = "The requested information could not be retrieved." if not result.success else "Tool result received."
            reply, hint = _language_safe_reply(user_message, fallback), None
        reply = _language_safe_reply(user_message, reply)
        return await self._finish(conversation_id, user_message, AgentResponse(reply=reply, tool_calls=[ToolCallSummary(name=name, success=result.success)], presentation_hint=hint))

    @staticmethod
    def _rate_limit_reply(info) -> str:
        retry_after = getattr(info, "retry_after", None) if info else None
        if retry_after:
            return f"The AI service is temporarily rate limited. Please try again after {retry_after}."
        return "The AI service is temporarily rate limited. Please try again shortly."

    async def _provider_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, object]],
        tool_choice: str,
        *,
        summary_present: bool = False,
        conversation_turns: int = 0,
        memory_count: int = 0,
        phase: str = "main",
    ):
        kwargs = {"tools": tools}
        if "tool_choice" in inspect.signature(self._llm_provider.chat).parameters:
            kwargs["tool_choice"] = tool_choice if tools else "none"
        response = await self._llm_provider.chat(messages, **kwargs)
        _trace_response(f"{phase}_llm_raw", response.content)
        try:
            sample = self._calibration.record(
                messages,
                tools,
                response,
                summary_present=summary_present,
                conversation_turns=conversation_turns,
                memory_count=memory_count,
                phase=phase,
            )
            aggregate = self._calibration.aggregate
            logger.info(
                "llm_prompt_calibration estimated=%s actual=%s absolute_difference=%s ratio=%s "
                "sample_count=%s average_ratio=%s min_ratio=%s max_ratio=%s "
                "conversation_turns=%s memory_count=%s summary_present=%s tool_count=%s",
                sample.estimated_prompt_tokens,
                sample.actual_prompt_tokens,
                sample.absolute_difference,
                sample.ratio,
                aggregate.sample_count,
                aggregate.average_ratio,
                aggregate.min_ratio,
                aggregate.max_ratio,
                sample.conversation_turns,
                sample.memory_count,
                sample.summary_present,
                sample.tool_count,
            )
        except Exception:
            logger.exception("llm_prompt_calibration_failed")
        return response

    async def _context_messages(self, conversation_id: str, all_history: bool = False) -> list[ConversationMessage]:
        if not self._conversations:
            return []
        recent = await self._conversations.list_recent(
            conversation_id,
            None if all_history else self._conversation_max_messages,
        )
        if all_history:
            return recent
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

    def _log_context_metrics(self, messages: list[ChatMessage], conversation_id: str, selection: ContextSelectionResult | None = None) -> None:
        system_messages = [item for item in messages if item.role == "system"]
        conversation_messages = [item for item in messages if item.role in ("user", "assistant")]
        tool_schema = self._tool_registry.get_llm_tools()
        logger.info(
            "llm_context_metrics conversation_id=%s persona_chars=%s memory_chars=%s conversation_chars=%s current_message_chars=%s tool_count=%s tool_schema_chars=%s estimated_context_tokens=%s context_budget=%s history_turns_selected=%s history_turns_dropped=%s memory_selected=%s",
            conversation_id,
            len(system_messages[0].content) if system_messages else 0,
            sum(len(item.content) for item in system_messages[1:]),
            sum(len(item.content) for item in conversation_messages[:-1]),
            len(conversation_messages[-1].content) if conversation_messages else 0,
            len(tool_schema),
            len(json.dumps(tool_schema, ensure_ascii=False)),
            selection.estimated_tokens if selection else None,
            selection.budget if selection else None,
            selection.selected_history_turns if selection else None,
            selection.dropped_turn_count if selection else None,
            selection.included_memory_count if selection else None,
        )

    async def _finish(self, conversation_id: str, user_message: str, response: AgentResponse) -> AgentResponse:
        _trace_response("final_user_response", response.reply)
        self._character_brain.observe(conversation_id, user_message, response)
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
