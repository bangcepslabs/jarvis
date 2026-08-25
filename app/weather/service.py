from app.weather.exceptions import WeatherError
from app.weather.models import ForecastDay, Location, WeatherSnapshot
from app.weather.open_meteo import OpenMeteoProvider


class WeatherService:
    def __init__(self, provider: OpenMeteoProvider, default_location: str | None = None) -> None:
        self._provider = provider
        self._default_location = default_location.strip() if default_location else None

    async def resolve_location(self, location: str | None) -> Location:
        query = (location or self._default_location or "").strip()
        if not query:
            raise WeatherError("Please provide a location for the weather request.")
        return await self._provider.geocode(query)

    async def current(self, location: str | None) -> WeatherSnapshot:
        return await self._provider.get_current_weather(await self.resolve_location(location))

    async def forecast(self, location: str | None, days: int, include_hourly: bool = False) -> list[ForecastDay]:
        return await self._provider.get_forecast(await self.resolve_location(location), days, include_hourly)
