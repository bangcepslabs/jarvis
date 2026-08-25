"""Real GPT-OSS curator and temporary persistence/personalization validation.

No secrets or raw personal values are printed. This script performs no retries.
"""
import asyncio
import json
import logging
from pathlib import Path

from app.agent.jarvis_agent import JarvisAgent
from app.agent.models import AgentResponse
from app.core.config import Settings
from app.llm.openai_provider import OpenAICompatibleProvider
from app.memory.curator import MemoryCurator
from app.memory.models import MemoryAction, MemoryCategory, MemoryDecision
from app.memory.service import MemoryService
from app.memory.sqlite_store import SQLiteMemoryStore
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry

logging.basicConfig(level=logging.WARNING)


async def main() -> None:
    base = Settings()
    if not base.llm_api_key:
        print("BLOCKED: LLM_API_KEY is not configured")
        return
    curator_settings = base.model_copy(update={
        "llm_provider": "openai",
        "llm_model": "qwen/qwen3.6-27b",
        "memory_curator_enabled": True,
        "memory_curator_model": "openai/gpt-oss-20b",
        "memory_curator_reasoning_effort": "low",
        "memory_curator_reasoning_format": "hidden",
        "memory_curator_temperature": 0.0,
        "memory_curator_max_completion_tokens": 128,
        "memory_curator_timeout_seconds": 10.0,
    })
    provider = OpenAICompatibleProvider(curator_settings)
    db_path = Path("data/jarvis_memory_validation.db")
    db_path.unlink(missing_ok=True)
    memory = MemoryService(SQLiteMemoryStore(str(db_path)))
    curator = MemoryCurator(provider, memory, curator_settings)
    cases = [
        ("Long-term preference", "나는 뉴스를 핵심만 짧게 보는 걸 좋아해.", "SAVE"),
        ("Temporary state", "오늘 너무 피곤하다.", "IGNORE"),
        ("Persistent environment", "우리 서버는 Ubuntu로 운영돼.", "SAVE"),
        ("Temporary preference", "오늘은 커피가 싫다.", "IGNORE"),
        ("Secret", "내 API key는 sk-example-secret 이야.", "IGNORE/BLOCK"),
    ]
    results = []
    stopped = False
    print("Preflight")
    print("application: JARVIS")
    print(f"version: {base.app_version}")
    print("main_model: qwen/qwen3.6-27b")
    print("memory_curator_enabled: true (validation override only)")
    print("memory_curator_model: openai/gpt-oss-20b")
    print("reasoning_effort: low")
    print("reasoning_format: hidden")
    print("temperature: 0.0")
    print("max_completion_tokens: 128")
    print("timeout: 10.0")
    print(f"validation_database: {db_path.name}")
    for name, user, expected in cases:
        decision = await curator.curate(user, "응답입니다.")
        actual = decision.action.value if decision else "NONE/ERROR"
        final = "IGNORE"
        if decision and decision.action != MemoryAction.IGNORE:
            persisted = await memory.apply_decision(decision)
            final = decision.action.value if persisted else "BLOCK/DUPLICATE"
        usage = curator.last_usage
        rate = curator.last_rate_limit
        print(f"usage prompt={getattr(usage, 'prompt_tokens', None)} completion={getattr(usage, 'completion_tokens', None)} total={getattr(usage, 'total_tokens', None)} finish_reason={curator.last_finish_reason} remaining_requests={getattr(rate, 'remaining_requests', None)} remaining_tokens={getattr(rate, 'remaining_tokens', None)} reset_tokens={getattr(rate, 'reset_tokens', None)} retry_after={getattr(rate, 'retry_after', None)}")
        print(f"{name}: expected={expected} curator={actual} final={final} PASS={actual in expected or final in expected}")
        results.append(actual in expected or final in expected)
        if decision is None:
            stopped = True
            print("429/invalid response: stopping subsequent real calls")
            break
        if decision and curator.last_rate_limit:
            info = curator.last_rate_limit
            print(f"rate_limit remaining_tokens={info.remaining_tokens} reset_tokens={info.reset_tokens} retry_after={info.retry_after}")
            if info.remaining_tokens is not None and info.remaining_tokens < 1500:
                print("TPM protection: stopping before next call")
                stopped = True
                break
    rows = await memory._store.list(100)
    print(f"Curator classification accuracy: {sum(results)}/{len(results)}")
    print(f"Persistence SAVE persisted: {len(rows) > 0}")
    print(f"adaptive rows: {sum(row.source.value == 'adaptive' for row in rows)}")
    before = len(rows)
    duplicate = await memory.apply_decision(MemoryDecision(action="SAVE", category=MemoryCategory.PREFERENCE, key="duplicate", value=rows[0].content if rows else "x"))
    after = len(await memory._store.list(100))
    print(f"Duplicate before={before} after={after} prevented={duplicate is None}")
    existing = rows[0] if rows else None
    update = await memory.apply_decision(MemoryDecision(action="UPDATE", category=existing.category if existing else MemoryCategory.PREFERENCE, key=existing.key if existing else "missing", value="updated durable value"))
    print(f"UPDATE existing={existing is not None} decision={update is not None} new_row={len(await memory._store.list(100)) != after}")

    if len(results) == len(cases) and all(results):
        # Main Qwen personalization uses the same validation DB but a fresh conversation id.
        main_settings = base.model_copy(update={"llm_model": "qwen/qwen3.6-27b", "llm_reasoning_effort": "none", "llm_temperature": 0.3, "llm_max_completion_tokens": 256})
        main_provider = OpenAICompatibleProvider(main_settings)
        agent_curator = MemoryCurator(main_provider, memory, curator_settings)
        agent = JarvisAgent(main_provider, ToolExecutor(ToolRegistry()), memory_service=memory, memory_curator=agent_curator)
        first = await agent.respond("앞으로 답변은 핵심만 짧게 말해줘.", "adaptive-memory-learn")
        second = await agent.respond("내 answer_style에 맞춰 답해줘.", "adaptive-memory-recall")
        print(f"Personalization turn1_response={bool(first.reply)} turn2_response={bool(second.reply)}")
        recalled = await memory.search_memories("answer_style")
        print(f"Personalization retrieved_memory_count={len(recalled)} context_injected={len(recalled) > 0}")
    else:
        print("Personalization: skipped because all five curator cases did not pass")


if __name__ == "__main__":
    asyncio.run(main())
