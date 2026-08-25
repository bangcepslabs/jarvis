class WeatherError(Exception):
    """Safe, user-facing weather provider failure."""


class WeatherUnavailableError(WeatherError):
    pass


class LocationNotFoundError(WeatherError):
    pass
