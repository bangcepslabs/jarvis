from typing import Literal

from pydantic import BaseModel, Field

from app.search.exceptions import SearchError
from app.search.service import SearchService
from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.models import ToolResult


class SearchArguments(BaseModel):
    query: str = Field(min_length=2, max_length=500, description="The focused web or news search query.")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum number of results to return, from 1 through 10.")
    time_range: Literal["day", "week", "month", "year"] | None = Field(default=None, description="Optional recency filter.")


class WebSearchTool(JarvisTool):
    name = "web_search"
    routing_hint = "Search the current web for information that may have changed or requires external sources. Not specifically recent news stories."
    description = """Search the current web for external information, documentation, products, or recent changes.

Use when current web sources are needed. Do NOT use specifically for recent news coverage; use search_news for that."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = SearchArguments

    def __init__(self, service: SearchService) -> None:
        self._service = service

    async def execute(self, arguments: SearchArguments) -> ToolResult:
        try:
            result = await self._service.web(arguments.query, arguments.max_results, arguments.time_range)
            return ToolResult(success=True, tool_name=self.name, data=result.model_dump(mode="json"))
        except SearchError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))


class NewsSearchTool(JarvisTool):
    name = "search_news"
    routing_hint = "Search recent news coverage when publication date, recency, or current events matter."
    description = """Search recent news coverage and current events.

Use when publication date, recency, or current events matter. Do NOT use for general documentation or stable web information."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = SearchArguments

    def __init__(self, service: SearchService) -> None:
        self._service = service

    async def execute(self, arguments: SearchArguments) -> ToolResult:
        try:
            result = await self._service.news(arguments.query, arguments.max_results, arguments.time_range)
            return ToolResult(success=True, tool_name=self.name, data=result.model_dump(mode="json"))
        except SearchError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))
