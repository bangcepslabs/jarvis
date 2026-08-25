from abc import ABC, abstractmethod

from app.search.models import SearchResponse


class SearchProvider(ABC):
    @abstractmethod
    async def search_web(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        raise NotImplementedError

    @abstractmethod
    async def search_news(self, query: str, max_results: int = 5, time_range: str | None = None) -> SearchResponse:
        raise NotImplementedError
