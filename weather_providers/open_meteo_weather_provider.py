from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
import shutil
import subprocess
import urllib.error
import urllib.request

from weather_providers.base_weather_provider import BaseWeatherProvider, WeatherResponse


class OpenMeteoWeatherProvider(BaseWeatherProvider):
    provider_name = "open-meteo"

    def __init__(
        self,
        geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search",
        forecast_url: str = "https://api.open-meteo.com/v1/forecast",
        timeout_seconds: int = 10,
    ) -> None:
        self.geocoding_url = geocoding_url
        self.forecast_url = forecast_url
        self.timeout_seconds = timeout_seconds

    def current_weather(self, city: str) -> WeatherResponse:
        city_name = city.strip()
        if not city_name:
            raise ValueError("城市名称不能为空")

        location = self._geocode(city_name)
        weather_payload, source_url = self._fetch_current_weather(location)
        current = weather_payload.get("current")
        if not isinstance(current, dict):
            raise RuntimeError("天气接口响应中缺少 current 数据")

        weather_code = self._optional_int(current.get("weather_code"))
        return WeatherResponse(
            city=str(location.get("name") or city_name),
            provider=self.provider_name,
            source_url=source_url,
            time=str(current.get("time") or ""),
            weather_text=self._weather_text(weather_code),
            temperature=self._optional_number(current.get("temperature_2m")),
            apparent_temperature=self._optional_number(current.get("apparent_temperature")),
            relative_humidity=self._optional_number(current.get("relative_humidity_2m")),
            precipitation=self._optional_number(current.get("precipitation")),
            wind_speed=self._optional_number(current.get("wind_speed_10m")),
            wind_direction=self._optional_number(current.get("wind_direction_10m")),
            latitude=self._optional_number(location.get("latitude")),
            longitude=self._optional_number(location.get("longitude")),
            weather_code=weather_code,
        )

    def _geocode(self, city: str) -> dict[str, Any]:
        url = f"{self.geocoding_url}?{urlencode({'name': city, 'count': 1, 'language': 'zh', 'format': 'json'})}"
        payload = self._fetch_json(url)
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise RuntimeError(f"未找到城市天气位置：{city}")
        first = results[0]
        if not isinstance(first, dict):
            raise RuntimeError(f"城市天气位置响应不可用：{city}")
        if first.get("latitude") is None or first.get("longitude") is None:
            raise RuntimeError(f"城市天气位置缺少经纬度：{city}")
        return first

    def _fetch_current_weather(self, location: dict[str, Any]) -> tuple[dict[str, Any], str]:
        params = {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ]
            ),
            "timezone": "auto",
        }
        url = f"{self.forecast_url}?{urlencode(params)}"
        return self._fetch_json(url), url

    def _fetch_json(self, url: str) -> dict[str, Any]:
        try:
            text = self._fetch_with_urllib(url)
        except RuntimeError:
            text = self._fetch_with_curl(url)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"天气接口响应不是有效 JSON：{exc}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("天气接口响应格式不可用")
        return parsed

    def _fetch_with_urllib(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"天气查询 urllib 失败：{exc}") from exc

    def _fetch_with_curl(self, url: str) -> str:
        curl_path = shutil.which("curl")
        if curl_path is None:
            raise RuntimeError("天气查询失败：curl 不可用")

        try:
            completed = subprocess.run(
                [curl_path, "--config", "-"],
                input=self._curl_config(url),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds + 5,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"天气查询 curl 超时：{self.timeout_seconds} 秒") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"天气查询 curl 失败：{detail}")

        body, status_code = self._split_curl_response(completed.stdout)
        if status_code >= 400:
            raise RuntimeError(f"天气查询 HTTP {status_code}: {body[:200]}")
        return body

    def _curl_config(self, url: str) -> str:
        lines = [
            "silent",
            "show-error",
            "location",
            "http1.1",
            f"max-time = {self.timeout_seconds}",
            "url = " + self._curl_config_value(url),
            "header = " + self._curl_config_value(f"User-Agent: {self._headers()['User-Agent']}"),
            "header = " + self._curl_config_value(f"Accept: {self._headers()['Accept']}"),
            "write-out = " + self._curl_config_value("\n%{http_code}"),
        ]
        return "\n".join(lines) + "\n"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "UTA/1.1 weather lookup",
            "Accept": "application/json",
        }

    @staticmethod
    def _weather_text(code: int | None) -> str:
        labels = {
            0: "晴",
            1: "晴间多云",
            2: "局部多云",
            3: "阴",
            45: "有雾",
            48: "雾凇",
            51: "小毛毛雨",
            53: "毛毛雨",
            55: "较强毛毛雨",
            56: "冻毛毛雨",
            57: "较强冻毛毛雨",
            61: "小雨",
            63: "中雨",
            65: "大雨",
            66: "冻雨",
            67: "较强冻雨",
            71: "小雪",
            73: "中雪",
            75: "大雪",
            77: "雪粒",
            80: "阵雨",
            81: "较强阵雨",
            82: "强阵雨",
            85: "阵雪",
            86: "强阵雪",
            95: "雷暴",
            96: "雷暴伴冰雹",
            99: "强雷暴伴冰雹",
        }
        return labels.get(code, "未知天气")

    @staticmethod
    def _optional_number(value: Any) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(number) if number.is_integer() else number

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        number = OpenMeteoWeatherProvider._optional_number(value)
        if number is None:
            return None
        return int(number)

    @staticmethod
    def _curl_config_value(value: str) -> str:
        escaped = (
            str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return f'"{escaped}"'

    @staticmethod
    def _split_curl_response(output: str) -> tuple[str, int]:
        body, separator, status_text = output.rpartition("\n")
        if not separator or not status_text.isdigit():
            raise RuntimeError("天气查询 curl 响应无 HTTP 状态码")
        return body, int(status_text)
