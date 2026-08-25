from pydantic import BaseModel


class Location(BaseModel):
    name: str
    country: str | None = None
    latitude: float
    longitude: float
    timezone: str


class WeatherSnapshot(BaseModel):
    location: str
    country: str | None = None
    observed_at: str
    timezone: str
    temperature: float | None = None
    apparent_temperature: float | None = None
    relative_humidity: float | None = None
    precipitation: float | None = None
    weather_code: int | None = None
    weather_description: str
    wind_speed: float | None = None
    source: str = "Open-Meteo"


class ForecastDay(BaseModel):
    date: str
    weather_description: str
    temperature_min: float | None = None
    temperature_max: float | None = None
    precipitation_probability: float | None = None
    precipitation_sum: float | None = None
    sunrise: str | None = None
    sunset: str | None = None


def weather_description(code: int | None) -> str:
    if code is None:
        return "Unknown conditions"
    if code == 0:
        return "Clear sky"
    if code in (1, 2, 3):
        return "Partly cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67):
        return "Rain"
    if code in (71, 73, 75, 77):
        return "Snow"
    if code in (80, 81, 82):
        return "Rain showers"
    if code in (85, 86):
        return "Snow showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown conditions"
