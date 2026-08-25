from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    source: str | None = None
    snippet: str = Field(default="", max_length=1500)
    published_at: str | None = None
    score: float | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SearchResponse(BaseModel):
    query: str
    topic: str
    results: list[SearchResult] = Field(default_factory=list)


def source_from_url(url: str) -> str | None:
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.") or None


def normalize_result(item: dict[str, Any]) -> SearchResult | None:
    title = item.get("title")
    url = item.get("url")
    if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    raw_snippet = item.get("content") or item.get("snippet") or ""
    snippet = str(raw_snippet)[:1500]
    published = item.get("published_date") or item.get("published_at")
    return SearchResult(title=title[:500], url=url, source=item.get("source") or source_from_url(url), snippet=snippet, published_at=str(published) if published else None, score=float(item["score"]) if isinstance(item.get("score"), (int, float)) else None)
