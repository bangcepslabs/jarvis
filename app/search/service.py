from app.search.provider import SearchProvider
from app.search.models import SearchResponse


class SearchService:
    def __init__(self, provider: SearchProvider, max_results: int = 5) -> None:
        self._provider = provider
        self._max_results = max(1, min(10, max_results))

    async def web(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        return await self._provider.search_web(query.strip(), min(max(1, max_results), self._max_results), time_range)

    async def news(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        return await self._provider.search_news(query.strip(), min(max(1, max_results), self._max_results), time_range)
