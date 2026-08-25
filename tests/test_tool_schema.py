from app.tools.docker.tools import GetContainerLogsTool, GetContainerStatusTool, ListContainersTool
from app.tools.system.status import SystemStatusTool
from app.tools.system.time import CurrentTimeTool
from app.weather.tools import CurrentWeatherTool, WeatherForecastTool


def test_tool_descriptions_define_semantic_boundaries():
    descriptions = [
        CurrentTimeTool.description,
        SystemStatusTool.description,
        ListContainersTool.description,
        GetContainerStatusTool.description,
        GetContainerLogsTool.description,
        CurrentWeatherTool.description,
        WeatherForecastTool.description,
    ]
    assert all("Use" in description and "Do NOT" in description for description in descriptions)
    assert "future-day forecasts" in CurrentWeatherTool.description
    assert "current weather conditions" in WeatherForecastTool.description


def test_weather_argument_schema_has_location_and_days_guidance():
    current = CurrentWeatherTool.__dict__["arguments_model"].model_json_schema()
    forecast = WeatherForecastTool.__dict__["arguments_model"].model_json_schema()
    assert "City or region" in current["properties"]["location"]["description"]
    assert "1 through 7" in forecast["properties"]["days"]["description"]
