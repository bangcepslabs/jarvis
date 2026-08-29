"""Configuration-driven context and conservative transcript correction helpers."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from collections.abc import Iterable, Mapping


def parse_terms(value: str | Iterable[str] | None, *, max_terms: int = 32, max_chars: int = 400) -> list[str]:
    """Return stable, de-duplicated terms suitable for a prompt."""
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else value
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        term = str(item).strip()
        key = term.casefold()
        if not term or key in seen:
            continue
        if len(result) >= max_terms:
            break
        seen.add(key)
        result.append(term)
    return result


def build_initial_prompt(terms: str | Iterable[str] | None, *, max_chars: int = 400) -> str | None:
    cleaned = parse_terms(terms, max_chars=max_chars)
    if not cleaned:
        return None
    prompt = ", ".join(cleaned)
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars].rsplit(",", 1)[0].strip()
    return prompt or None


def parse_alias_map(value: str | None) -> dict[str, list[str]]:
    if not value or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    result: dict[str, list[str]] = {}
    for canonical, aliases in decoded.items():
        name = str(canonical).strip()
        if not name:
            continue
        result[name] = parse_terms(aliases if isinstance(aliases, list) else [aliases], max_terms=16, max_chars=160)
    return result


def correct_transcript(raw_text: str, known_terms: Mapping[str, Iterable[str]] | Iterable[str] | None) -> str:
    """Conservatively fix only registered aliases; otherwise return raw_text."""
    if not raw_text or not known_terms:
        return raw_text
    aliases: dict[str, str] = {}
    if isinstance(known_terms, Mapping):
        for canonical, values in known_terms.items():
            for alias in values:
                alias_text = str(alias).strip()
                if alias_text:
                    aliases[alias_text.casefold()] = str(canonical)
    else:
        for term in known_terms:
            text = str(term).strip()
            if text:
                aliases[text.casefold()] = text
    if not aliases:
        return raw_text

    result = raw_text
    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if len(alias) < 2:
            continue
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        result = pattern.sub(canonical, result)

    # Handle short one-token recognition errors such as a registered alias that
    # differs by one character, without fuzzy-matching arbitrary sentences.
    for token in re.findall(r"[\w가-힣-]+", result):
        token_key = token.casefold()
        if token_key in aliases or len(token) < 3:
            continue
        candidates = [(alias, canonical) for alias, canonical in aliases.items() if len(alias) >= 3]
        best = max(candidates, key=lambda item: SequenceMatcher(None, token_key, item[0]).ratio(), default=None)
        if best and SequenceMatcher(None, token_key, best[0]).ratio() >= 0.88:
            result = re.sub(re.escape(token), best[1], result, count=1, flags=re.IGNORECASE)
    return result
