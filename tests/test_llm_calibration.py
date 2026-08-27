from app.agent.jarvis_agent import JarvisAgent
import pytest

from app.agent.models import ChatMessage
from app.llm.base import LLMProvider
from app.llm.calibration import LLMCalibrationCollector
from app.llm.models import LLMResponse, LLMUsage
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


def _messages(text: str = "hello"):
    return [ChatMessage(role="system", content="system"), ChatMessage(role="user", content=text)]


def test_estimate_lower_than_actual():
    collector = LLMCalibrationCollector()
    sample = collector.record(_messages(), [], LLMResponse(usage=LLMUsage(prompt_tokens=100)))
    assert sample.actual_prompt_tokens > sample.estimated_prompt_tokens
    assert sample.absolute_difference == 100 - sample.estimated_prompt_tokens
    assert sample.ratio == 100 / sample.estimated_prompt_tokens


def test_estimate_higher_than_actual():
    collector = LLMCalibrationCollector()
    estimated = collector.estimate_prompt(_messages(), [])
    sample = collector.record(_messages(), [], LLMResponse(usage=LLMUsage(prompt_tokens=1)))
    assert sample.estimated_prompt_tokens == estimated
    assert sample.absolute_difference == estimated - 1


def test_estimate_equal_actual():
    collector = LLMCalibrationCollector()
    estimated = collector.estimate_prompt(_messages(), [])
    sample = collector.record(_messages(), [], LLMResponse(usage=LLMUsage(prompt_tokens=estimated)))
    assert sample.absolute_difference == 0
    assert sample.ratio == 1


def test_zero_estimate_is_safe():
    collector = LLMCalibrationCollector()
    collector.estimate_prompt = lambda messages, tools: 0
    sample = collector.record(_messages(), [], LLMResponse(usage=LLMUsage(prompt_tokens=10)))
    assert sample.ratio is None


def test_missing_usage_is_observable_without_failure():
    collector = LLMCalibrationCollector()
    sample = collector.record(_messages(), [], LLMResponse())
    assert sample.actual_prompt_tokens is None
    assert sample.absolute_difference is None
    assert collector.aggregate.sample_count == 0


def test_aggregate_ratio_statistics():
    collector = LLMCalibrationCollector()
    estimated = collector.estimate_prompt(_messages(), [])
    for actual in (estimated, estimated * 2, estimated // 2):
        collector.record(_messages(), [], LLMResponse(usage=LLMUsage(prompt_tokens=actual)))
    aggregate = collector.aggregate
    assert aggregate.sample_count == 3
    assert aggregate.average_ratio == pytest.approx((1 + 2 + 0.5) / 3)
    assert aggregate.min_ratio == 0.5
    assert aggregate.max_ratio == 2


def test_tool_and_summary_metadata_are_recorded():
    collector = LLMCalibrationCollector()
    without_tools = collector.estimate_prompt(_messages(), [])
    with_tools = collector.estimate_prompt(
        _messages(), [{"type": "function", "function": {"name": "weather"}}]
    )
    assert with_tools > without_tools
    sample = collector.record(
        _messages(),
        [{"type": "function", "function": {"name": "weather"}}],
        LLMResponse(usage=LLMUsage(prompt_tokens=20)),
        summary_present=True,
        conversation_turns=8,
        memory_count=3,
    )
    assert sample.tool_count == 1
    assert sample.summary_present is True
    assert sample.conversation_turns == 8
    assert sample.memory_count == 3


class ResponseProvider(LLMProvider):
    async def chat(self, messages, tools=None, tool_choice=None):
        return LLMResponse(content="ok", usage=LLMUsage(prompt_tokens=10))


def test_calibration_failure_does_not_block_agent_provider_response():
    collector = LLMCalibrationCollector()
    collector.record = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("metrics failed"))
    agent = JarvisAgent(ResponseProvider(), ToolExecutor(ToolRegistry()), calibration=collector)
    import asyncio

    response = asyncio.run(agent.respond("hello"))
    assert response.reply == "ok"
