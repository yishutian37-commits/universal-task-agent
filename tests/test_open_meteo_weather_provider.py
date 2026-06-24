from weather_providers.open_meteo_weather_provider import OpenMeteoWeatherProvider


class FakeOpenMeteoWeatherProvider(OpenMeteoWeatherProvider):
    def __init__(self):
        super().__init__(timeout_seconds=1)
        self.urls = []

    def _fetch_json(self, url):
        self.urls.append(url)
        if "geocoding-api.open-meteo.com" in url:
            return {
                "results": [
                    {
                        "name": "包头",
                        "country": "中国",
                        "latitude": 40.6522,
                        "longitude": 109.8222,
                    }
                ]
            }
        return {
            "current": {
                "time": "2026-06-24T14:00",
                "temperature_2m": 23.4,
                "apparent_temperature": 22.8,
                "relative_humidity_2m": 41,
                "precipitation": 0,
                "weather_code": 1,
                "wind_speed_10m": 12.5,
                "wind_direction_10m": 270,
            }
        }


def test_open_meteo_provider_returns_normalized_weather():
    provider = FakeOpenMeteoWeatherProvider()

    weather = provider.current_weather("包头")

    assert weather.city == "包头"
    assert weather.provider == "open-meteo"
    assert weather.weather_text == "晴间多云"
    assert weather.temperature == 23.4
    assert weather.apparent_temperature == 22.8
    assert weather.relative_humidity == 41
    assert weather.precipitation == 0
    assert weather.wind_speed == 12.5
    assert weather.wind_direction == 270
    assert "latitude=40.6522" in provider.urls[1]
    assert "current=temperature_2m" in provider.urls[1]
