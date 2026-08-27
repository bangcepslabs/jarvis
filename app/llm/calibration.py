import json
from dataclasses import dataclass
from typing import Any

from app.agent.models import ChatMessage
from app.conversation.context import EstimatedTokenCounter
from app.llm.models import LLMResponse


@dataclass(frozen=True)
class CalibrationSample:
    estimated_prompt_tokens: int
    actual_prompt_tokens: int | None
    absolute_difference: int | None
    ratio: float | None
    tool_count: int
    summary_present: bool
    conversation_turns: int
    memory_count: int


@dataclass(frozen=True)
class CalibrationAggregate:
    sample_count: int
    average_ratio: float | None
    min_ratio: float | None
    max_ratio: float | None


class LLMCalibrationCollector:
    """In-memory, best-effort comparison of estimates and provider usage."""

    def __init__(self) -> None:
        self._samples: list[CalibrationSample] = []

    @staticmethod
    def estimate_prompt(messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None) -> int:
        estimate = sum(EstimatedTokenCounter.estimate_message(message) for message in messages)
        if tools:
            schema = json.dumps(tools, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            estimate += EstimatedTokenCounter.estimate(schema, "system")
        return estimate

    def record(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        response: LLMResponse | None,
        *,
        summary_present: bool = False,
        conversation_turns: int = 0,
        memory_count: int = 0,
    ) -> CalibrationSample:
        estimated = self.estimate_prompt(messages, tools)
        actual = getattr(response.usage, "prompt_tokens", None) if response and response.usage else None
        difference = abs(actual - estimated) if actual is not None else None
        ratio = actual / estimated if actual is not None and estimated > 0 else None
        sample = CalibrationSample(
            estimated_prompt_tokens=estimated,
            actual_prompt_tokens=actual,
            absolute_difference=difference,
            ratio=ratio,
            tool_count=len(tools or []),
            summary_present=summary_present,
            conversation_turns=conversation_turns,
            memory_count=memory_count,
        )
        self._samples.append(sample)
        return sample

    @property
    def samples(self) -> tuple[CalibrationSample, ...]:
        return tuple(self._samples)

    @property
    def aggregate(self) -> CalibrationAggregate:
        ratios = [sample.ratio for sample in self._samples if sample.ratio is not None]
        return CalibrationAggregate(
            sample_count=len(ratios),
            average_ratio=sum(ratios) / len(ratios) if ratios else None,
            min_ratio=min(ratios) if ratios else None,
            max_ratio=max(ratios) if ratios else None,
        )
