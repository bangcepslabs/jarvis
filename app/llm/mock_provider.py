import json
import re

from app.agent.models import ChatMessage
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse, LLMToolCall


def _text(*code_points: int) -> str:
    return "".join(chr(code_point) for code_point in code_points)


TIME_INTENTS = (
    _text(0xC9C0, 0xAE08, 0x20, 0xBA87, 0x20, 0xC2DC),
    _text(0xD604, 0xC7AC, 0x20, 0xC2DC, 0xAC04),
    _text(0xC2DC, 0xAC04, 0x20, 0xC54C, 0xB824, 0xC918),
    _text(0xBC8C, 0xC368, 0x20, 0xC624, 0xD6C4),
    _text(0xC624, 0xB298, 0x20, 0xB0A0, 0xC9DC),
)
STATUS_INTENTS = (
    _text(0xC11C, 0xBC84, 0x20, 0xC0C1, 0xD0DC),
    _text(0xCEF4, 0xD4E8, 0xD130, 0x20, 0xC65C, 0x20, 0xC774, 0xB807, 0xAC8C),
    _text(0xBA54, 0xBAA8, 0xB9AC, 0xAC00, 0x20, 0xB9CE, 0xC774),
    "cpu",
)
DOCKER_LIST_INTENTS = (
    _text(0xB3C4, 0xCEE4, 0x20, 0xBAA9, 0xB85D),
    _text(0xC2E4, 0xD589, 0x20, 0xC911, 0xC778, 0x20, 0xCEE8, 0xD14C, 0xC774, 0xB108),
)
STATUS_WORD = _text(0xC0C1, 0xD0DC)
LOG_WORD = _text(0xB85C, 0xADF8)
RESTART_WORD = _text(0xC7AC, 0xC2DC, 0xC791)
WEATHER_WORDS = ("weather", "forecast", _text(0xB0A0, 0xC528), _text(0xBE44, 0xC608, 0xBCF4))
FORECAST_WORDS = ("forecast", "tomorrow", _text(0xB0B4, 0xC77C), _text(0xC8FC, 0xB9D0))


class MockLLMProvider(LLMProvider):
    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, object]] | None = None, tool_choice: str | dict[str, object] | None = None, response_format: dict[str, object] | None = None, **kwargs) -> LLMResponse:
        if messages and messages[-1].role == "tool":
            try:
                data = json.loads(messages[-1].content)
                if data.get("success"):
                    return LLMResponse(content=f"Tool result received: {data.get('data', {})}")
                return LLMResponse(content="The requested information could not be retrieved.")
            except (TypeError, json.JSONDecodeError):
                return LLMResponse(content="The requested information could not be retrieved.")

        latest_message = next((message.content for message in reversed(messages) if message.role == "user"), "")
        if not latest_message and messages:
            marker = "Current request:"
            content = messages[-1].content
            if marker in content:
                latest_message = content.split(marker, 1)[1].lstrip("\r\n").splitlines()[0].strip()
            else:
                latest_message = content
        normalized = latest_message.casefold()
        tool_names = {str(item.get("name")) for item in (tools or [])}
        if response_format:
            route = None
            if any(phrase in normalized for phrase in TIME_INTENTS):
                route = "get_current_time"
            elif any(word in normalized for word in FORECAST_WORDS) and any(word in normalized for word in WEATHER_WORDS):
                route = "get_weather_forecast"
            elif any(word in normalized for word in WEATHER_WORDS):
                route = "get_current_weather"
            elif any(phrase in normalized for phrase in STATUS_INTENTS):
                route = "get_system_status"
            return LLMResponse(content=json.dumps({"tool_name": route}, ensure_ascii=False), finish_reason="stop")
        if any(word in normalized for word in WEATHER_WORDS) and ({"get_current_weather", "get_weather_forecast"} & tool_names):
            location = _weather_location(latest_message)
            if any(word in normalized for word in FORECAST_WORDS) and "get_weather_forecast" in tool_names:
                return LLMResponse(tool_calls=[LLMToolCall(id="mock-weather-forecast", name="get_weather_forecast", arguments={"location": location} if location else {})], finish_reason="tool_calls")
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-weather-current", name="get_current_weather", arguments={"location": location} if location else {})], finish_reason="tool_calls")
        if any(word in normalized for word in WEATHER_WORDS):
            return LLMResponse(content="Live weather lookup is not connected yet.")
        if tools and any(phrase in normalized for phrase in TIME_INTENTS):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-time", name="get_current_time")], finish_reason="tool_calls")
        if tools and any(phrase in normalized for phrase in DOCKER_LIST_INTENTS):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-docker-list", name="list_containers")], finish_reason="tool_calls")
        if tools and ("restart" in normalized or RESTART_WORD in normalized):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-docker-restart", name="restart_container", arguments={"container": _container_name(latest_message)})], finish_reason="tool_calls")
        if tools and ("log" in normalized or LOG_WORD in normalized):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-docker-logs", name="get_container_logs", arguments={"container": _container_name(latest_message)})], finish_reason="tool_calls")
        if tools and any(word in normalized for word in ("status", STATUS_WORD)) and _container_name(latest_message):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-docker-status", name="get_container_status", arguments={"container": _container_name(latest_message)})], finish_reason="tool_calls")
        if tools and any(phrase in normalized for phrase in STATUS_INTENTS):
            return LLMResponse(tool_calls=[LLMToolCall(id="mock-status", name="get_system_status")], finish_reason="tool_calls")
        return LLMResponse(content=f"JARVIS development mode received: {latest_message}")


def _container_name(message: str) -> str:
    matches = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_.-]*\b", message)
    excluded = {"docker", "container", "status", "logs", "log", "show", "the", "is", "cpu"}
    return next((item for item in matches if item.casefold() not in excluded), "")


def _weather_location(message: str) -> str:
    matches = re.findall(r"\b[a-zA-Z][a-zA-Z -]{1,40}\b", message)
    excluded = {"weather", "forecast", "today", "tomorrow", "what", "is", "the", "for", "in"}
    return next((item.strip() for item in matches if item.casefold().strip() not in excluded), "")
