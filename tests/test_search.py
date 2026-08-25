import pytest

from app.search.exceptions import SearchUnavailableError
from app.search.models import SearchResponse, normalize_result
from app.search.service import SearchService
from app.search.tools import NewsSearchTool, WebSearchTool


class FakeSearchProvider:
    async def search_web(self, query, max_results=5, time_range=None):
        return SearchResponse(query=query, topic="general", results=[normalize_result({"title": "Docs", "url": "https://example.com/docs", "content": "A result."})])

    async def search_news(self, query, max_results=5, time_range=None):
        return SearchResponse(query=query, topic="news", results=[normalize_result({"title": "News", "url": "https://news.example/article", "content": "A news result.", "published_date": "2026-08-25T00:00:00Z"})])


@pytest.mark.asyncio
async def test_web_search_tool_normalizes_sources() -> None:
    result = await WebSearchTool(SearchService(FakeSearchProvider())).execute(type("Args", (), {"query": "FastAPI", "max_results": 5, "time_range": None})())
    assert result.success is True
    assert result.data["results"][0]["source"] == "example.com"


@pytest.mark.asyncio
async def test_news_search_preserves_published_at() -> None:
    result = await NewsSearchTool(SearchService(FakeSearchProvider())).execute(type("Args", (), {"query": "AI news", "max_results": 5, "time_range": "day"})())
    assert result.success is True
    assert result.data["results"][0]["published_at"] == "2026-08-25T00:00:00Z"


def test_search_result_rejects_invalid_url() -> None:
    assert normalize_result({"title": "bad", "url": "file:///secret", "content": "x"}) is None


class FailingProvider(FakeSearchProvider):
    async def search_news(self, query, max_results=5, time_range=None):
        raise SearchUnavailableError("The search service is currently unavailable.")


@pytest.mark.asyncio
async def test_search_tool_translates_provider_failure() -> None:
    result = await NewsSearchTool(SearchService(FailingProvider())).execute(type("Args", (), {"query": "AI", "max_results": 5, "time_range": None})())
    assert result.success is False
    assert result.error == "The search service is currently unavailable."
