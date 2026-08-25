from pydantic import BaseModel, Field

from app.tools.base import JarvisTool, ToolSafetyLevel
from app.tools.models import ToolResult
from app.weather.exceptions import WeatherError
from app.weather.service import WeatherService


class CurrentWeatherArguments(BaseModel):
    location: str | None = Field(default=None, min_length=1, max_length=120, description="City or region, for example Busan, Seoul, or Tokyo.")


class ForecastArguments(CurrentWeatherArguments):
    days: int = Field(default=3, ge=1, le=7, description="Number of forecast days, from 1 through 7.")
    include_hourly: bool = Field(default=False, description="Include a bounded hourly forecast when explicitly requested.")


class CurrentWeatherTool(JarvisTool):
    name = "get_current_weather"
    routing_hint = "Current weather conditions for a location."
    description = """Get current weather conditions for a location.

Use for weather now, temperature, rain, humidity, wind, or current conditions.
Do NOT use for future-day forecasts such as tomorrow or the weekend."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = CurrentWeatherArguments

    def __init__(self, service: WeatherService) -> None:
        self._service = service

    async def execute(self, arguments: CurrentWeatherArguments) -> ToolResult:
        try:
            result = await self._service.current(arguments.location)
            return ToolResult(success=True, tool_name=self.name, data=result.model_dump())
        except WeatherError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))


class WeatherForecastTool(JarvisTool):
    name = "get_weather_forecast"
    routing_hint = "Future weather such as later today, tomorrow, or the weekend."
    description = """Get future weather forecasts for a location.

Use for later today, tonight, tomorrow, this weekend, or the next several days.
Do NOT use solely for current weather conditions."""
    safety_level = ToolSafetyLevel.READ_ONLY
    arguments_model = ForecastArguments

    def __init__(self, service: WeatherService, max_days: int = 7) -> None:
        self._service = service
        self._max_days = max(1, min(7, max_days))

    async def execute(self, arguments: ForecastArguments) -> ToolResult:
        if arguments.days > self._max_days:
            return ToolResult(success=False, tool_name=self.name, error=f"Forecast is limited to {self._max_days} days.")
        try:
            forecast = await self._service.forecast(arguments.location, arguments.days, arguments.include_hourly)
            return ToolResult(success=True, tool_name=self.name, data={"forecast": [item.model_dump() for item in forecast], "source": "Open-Meteo"})
        except WeatherError as exc:
            return ToolResult(success=False, tool_name=self.name, error=str(exc))
