import httpx
import pytest

from app.weather.models import Location
from app.weather.open_meteo import OpenMeteoProvider
from app.weather.service import WeatherService
from app.weather.tools import CurrentWeatherArguments, CurrentWeatherTool, ForecastArguments, WeatherForecastTool


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        self.calls.append((url, params))
        if "geocoding" in url:
            return httpx.Response(200, request=httpx.Request("GET", url), json={"results": [{"name": "Seoul", "country": "South Korea", "latitude": 37.5, "longitude": 127.0, "timezone": "Asia/Seoul"}]})
        return httpx.Response(200, request=httpx.Request("GET", url), json={"current": {"time": "2026-08-20T10:00", "temperature_2m": 28.1, "apparent_temperature": 30.3, "relative_humidity_2m": 60, "precipitation": 0, "weather_code": 2, "wind_speed_10m": 4}, "daily": {"time": ["2026-08-20"], "weather_code": [2], "temperature_2m_min": [23], "temperature_2m_max": [30], "precipitation_probability_max": [20], "precipitation_sum": [0], "sunrise": ["06:00"], "sunset": ["19:30"]}})


@pytest.mark.asyncio
async def test_open_meteo_current_and_forecast_parsing(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)
    provider = OpenMeteoProvider()
    location = await provider.geocode("Seoul")
    current = await provider.get_current_weather(location)
    forecast = await provider.get_forecast(location, 1)
    assert location.timezone == "Asia/Seoul"
    assert current.temperature == 28.1
    assert current.weather_description == "Partly cloudy"
    assert forecast[0].temperature_max == 30


@pytest.mark.asyncio
async def test_weather_tool_default_location_and_validation():
    class Provider:
        async def geocode(self, query):
            return Location(name=query, latitude=1, longitude=2, timezone="UTC")
        async def get_current_weather(self, location):
            from app.weather.models import WeatherSnapshot
            return WeatherSnapshot(location=location.name, observed_at="now", timezone="UTC", weather_description="Clear sky")
        async def get_forecast(self, location, days, include_hourly=False):
            return []

    service = WeatherService(Provider(), "Seoul")
    result = await CurrentWeatherTool(service).execute(CurrentWeatherArguments())
    assert result.success and result.data["location"] == "Seoul"
    forecast = await WeatherForecastTool(service).execute(ForecastArguments(days=7))
    assert forecast.success
    with pytest.raises(ValueError):
        ForecastArguments(days=8)
