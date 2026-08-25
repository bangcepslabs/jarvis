import json
import logging
from typing import Any

import httpx

from app.agent.models import ChatMessage
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.exceptions import LLMProviderError, LLMRateLimitError
from app.llm.models import LLMRateLimitInfo, LLMResponse, LLMToolCall, LLMUsage

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI Chat Completions compatible adapter using httpx only."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMProviderError("LLM API key is not configured.")
        self._settings = settings
        base_url = settings.llm_base_url.rstrip("/")
        self._chat_url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        self.last_error_metadata: dict[str, object] = {}

    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, object]] | None = None, tool_choice: str | dict[str, object] | None = None, response_format: dict[str, object] | None = None, model: str | None = None, temperature: float | None = None, max_completion_tokens: int | None = None, reasoning_effort: str | None = None, reasoning_format: str | None = None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model or self._settings.llm_model,
            "messages": [self._serialize_message(message) for message in messages],
        }
        request_reasoning = reasoning_effort if reasoning_effort is not None else self._settings.llm_reasoning_effort
        if request_reasoning:
            payload["reasoning_effort"] = request_reasoning
        token_limit = max_completion_tokens if max_completion_tokens is not None else self._settings.llm_max_completion_tokens
        if token_limit:
            payload["max_completion_tokens"] = token_limit
        request_temperature = temperature if temperature is not None else self._settings.llm_temperature
        if request_temperature is not None:
            payload["temperature"] = request_temperature
        if response_format:
            payload["response_format"] = response_format
        if reasoning_format:
            payload["reasoning_format"] = reasoning_format
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or ("auto" if tools else "none")
            if tools:
                payload["parallel_tool_calls"] = False
        headers = {"Authorization": f"Bearer {self._settings.llm_api_key}", "Content-Type": "application/json"}
        logger.info("llm_request_started provider=openai_compatible")
        try:
            async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
                response = await client.post(self._chat_url, json=payload, headers=headers)
                rate_limit = self._parse_rate_limit(getattr(response, "headers", {}))
                if getattr(response, "status_code", 200) == 429:
                    raise LLMRateLimitError(rate_limit=self._rate_limit_message(rate_limit))
                if getattr(response, "status_code", 200) >= 400:
                    self.last_error_metadata = self._safe_error_metadata(response)
                response.raise_for_status()
                body = response.json()
        except LLMRateLimitError as exc:
            logger.warning("llm_rate_limited provider=openai_compatible retry_after=%s remaining_requests=%s remaining_tokens=%s", getattr(exc.rate_limit, "retry_after", None), getattr(exc.rate_limit, "remaining_requests", None), getattr(exc.rate_limit, "remaining_tokens", None))
            raise
        except (httpx.HTTPError, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.exception("provider_error provider=openai_compatible status=%s", status)
            raise LLMProviderError("The AI service is currently unavailable.") from exc
        try:
            message = body["choices"][0]["message"]
            calls = [self._parse_tool_call(item) for item in message.get("tool_calls", [])]
            usage = body.get("usage")
            result = LLMResponse(content=message.get("content"), tool_calls=calls, finish_reason=body["choices"][0].get("finish_reason"), usage=LLMUsage(**usage) if isinstance(usage, dict) else None, rate_limit=rate_limit)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("The AI service returned an invalid response.") from exc
        logger.info("llm_request_completed provider=openai_compatible model=%s tool_calls=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s remaining_requests=%s remaining_tokens=%s", self._settings.llm_model, len(result.tool_calls), getattr(result.usage, "prompt_tokens", None), getattr(result.usage, "completion_tokens", None), getattr(result.usage, "total_tokens", None), getattr(result.rate_limit, "remaining_requests", None), getattr(result.rate_limit, "remaining_tokens", None))
        return result

    @staticmethod
    def _safe_error_metadata(response) -> dict[str, object]:
        try:
            body = response.json()
        except (ValueError, TypeError):
            return {"http_status": getattr(response, "status_code", None)}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if not isinstance(error, dict):
            error = {}
        failed = error.get("failed_generation")
        return {
            "http_status": getattr(response, "status_code", None),
            "error_type": error.get("type"),
            "error_code": error.get("code"),
            "error_message": error.get("message"),
            "failed_generation_reason": failed.get("reason") if isinstance(failed, dict) else None,
        }

    @staticmethod
    def _parse_rate_limit(headers) -> LLMRateLimitInfo:
        def integer(name: str) -> int | None:
            value = headers.get(name)
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        return LLMRateLimitInfo(
            remaining_requests=integer("x-ratelimit-remaining-requests"),
            remaining_tokens=integer("x-ratelimit-remaining-tokens"),
            reset_requests=headers.get("x-ratelimit-reset-requests"),
            reset_tokens=headers.get("x-ratelimit-reset-tokens"),
            retry_after=headers.get("retry-after"),
        )

    @staticmethod
    def _rate_limit_message(info: LLMRateLimitInfo) -> LLMRateLimitInfo:
        return info

    @staticmethod
    def _serialize_message(message: ChatMessage) -> dict[str, Any]:
        result: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "tool":
            result["tool_call_id"] = message.tool_call_id
            if message.name:
                result["name"] = message.name
        if message.role == "assistant" and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                if hasattr(call, "id")
                else call
                for call in message.tool_calls
            ]
        return result

    @staticmethod
    def _parse_tool_call(item: dict[str, Any]) -> LLMToolCall:
        function = item.get("function", {})
        raw_arguments = function.get("arguments", {})
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        except json.JSONDecodeError:
            arguments = {}
        return LLMToolCall(id=item.get("id"), name=function.get("name", ""), arguments=arguments if isinstance(arguments, dict) else {})
