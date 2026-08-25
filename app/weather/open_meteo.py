import httpx

from app.weather.exceptions import LocationNotFoundError, WeatherUnavailableError
from app.weather.models import ForecastDay, Location, WeatherSnapshot, weather_description


class OpenMeteoProvider:
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    forecast_url = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout = timeout_seconds

    async def geocode(self, query: str) -> Location:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.geocoding_url, params={"name": query, "count": 1, "language": "en", "format": "json"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise WeatherUnavailableError("Weather service is currently unavailable.") from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            raise LocationNotFoundError(f"Location '{query}' was not found.")
        item = results[0]
        try:
            return Location(name=item["name"], country=item.get("country"), latitude=float(item["latitude"]), longitude=float(item["longitude"]), timezone=item.get("timezone", "UTC"))
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherUnavailableError("Weather service returned an invalid location.") from exc

    async def get_current_weather(self, location: Location) -> WeatherSnapshot:
        payload = await self._forecast_payload(location, {"current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m", "forecast_days": 1})
        current = payload.get("current", {})
        code = current.get("weather_code")
        return WeatherSnapshot(location=location.name, country=location.country, observed_at=str(current.get("time", "")), timezone=location.timezone, temperature=current.get("temperature_2m"), apparent_temperature=current.get("apparent_temperature"), relative_humidity=current.get("relative_humidity_2m"), precipitation=current.get("precipitation"), weather_code=code, weather_description=weather_description(code), wind_speed=current.get("wind_speed_10m"))

    async def get_forecast(self, location: Location, days: int, include_hourly: bool = False) -> list[ForecastDay]:
        variables = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,sunrise,sunset"
        payload = await self._forecast_payload(location, {"daily": variables, "forecast_days": days, "timezone": "auto", **({"hourly": "temperature_2m,precipitation_probability,weather_code"} if include_hourly else {})})
        daily = payload.get("daily", {})
        try:
            return [ForecastDay(date=date, weather_description=weather_description(code), temperature_min=lo, temperature_max=hi, precipitation_probability=prob, precipitation_sum=rain, sunrise=sunrise, sunset=sunset) for date, code, lo, hi, prob, rain, sunrise, sunset in zip(daily["time"], daily.get("weather_code", []), daily.get("temperature_2m_min", []), daily.get("temperature_2m_max", []), daily.get("precipitation_probability_max", []), daily.get("precipitation_sum", []), daily.get("sunrise", []), daily.get("sunset", []))]
        except (KeyError, TypeError) as exc:
            raise WeatherUnavailableError("Weather service returned an invalid forecast.") from exc

    async def _forecast_payload(self, location: Location, params: dict[str, object]) -> dict:
        query = {"latitude": location.latitude, "longitude": location.longitude, **params}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.forecast_url, params=query)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise WeatherUnavailableError("Weather service is currently unavailable.") from exc
        if not isinstance(payload, dict):
            raise WeatherUnavailableError("Weather service returned an invalid response.")
        return payload
