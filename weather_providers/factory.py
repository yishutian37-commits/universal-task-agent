from __future__ import annotations

import os

from weather_providers.base_weather_provider import BaseWeatherProvider
from weather_providers.open_meteo_weather_provider import OpenMeteoWeatherProvider


def build_weather_provider() -> BaseWeatherProvider:
    provider = os.getenv("WEATHER_PROVIDER", "open-meteo").strip().lower()
    if provider in {"open-meteo", "open_meteo", "openmeteo"}:
        return OpenMeteoWeatherProvider(
            timeout_seconds=int(os.getenv("WEATHER_TIMEOUT_SECONDS", "10")),
        )
    raise ValueError(f"Unsupported WEATHER_PROVIDER: {provider}")
