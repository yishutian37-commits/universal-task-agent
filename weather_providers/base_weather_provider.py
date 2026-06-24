from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WeatherResponse:
    city: str
    provider: str
    source_url: str
    time: str
    weather_text: str
    temperature: float | int | None = None
    apparent_temperature: float | int | None = None
    relative_humidity: float | int | None = None
    precipitation: float | int | None = None
    wind_speed: float | int | None = None
    wind_direction: float | int | None = None
    latitude: float | int | None = None
    longitude: float | int | None = None
    weather_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseWeatherProvider:
    provider_name = "base-weather"

    def current_weather(self, city: str) -> WeatherResponse:
        raise NotImplementedError


def weather_to_dict(response: WeatherResponse | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, WeatherResponse):
        return response.to_dict()
    return dict(response)
