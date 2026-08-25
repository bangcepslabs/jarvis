import logging
from time import perf_counter

import httpx

from app.search.exceptions import SearchNoResultsError, SearchUnavailableError
from app.search.models import SearchResponse, normalize_result
from app.search.provider import SearchProvider

logger = logging.getLogger(__name__)


class TavilySearchProvider(SearchProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.tavily.com", timeout_seconds: float = 8.0) -> None:
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/search"
        self._timeout = timeout_seconds

    async def search_web(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        return await self._search(query, "general", max_results, time_range)

    async def search_news(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        return await self._search(query, "news", max_results, time_range)

    async def _search(self, query: str, topic: str, max_results: int, time_range: str | None) -> SearchResponse:
        payload = {"api_key": self._api_key, "query": query, "topic": topic, "search_depth": "basic", "max_results": max_results, "include_answer": False, "include_raw_content": False}
        if time_range:
            payload["time_range"] = time_range
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("search_failed provider=tavily topic=%s", topic)
            raise SearchUnavailableError("The search service is currently unavailable.") from exc
        raw_results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(raw_results, list):
            raise SearchUnavailableError("The search service returned an invalid response.")
        results = [item for item in (normalize_result(value) for value in raw_results if isinstance(value, dict)) if item is not None][:max_results]
        logger.info("search_completed provider=tavily topic=%s result_count=%s elapsed_ms=%s", topic, len(results), round((perf_counter() - started) * 1000, 2))
        if not results:
            raise SearchNoResultsError("No search results were found.")
        return SearchResponse(query=query, topic=topic, results=results)
