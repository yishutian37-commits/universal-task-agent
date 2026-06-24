from __future__ import annotations

import re
from typing import Any

from search_providers.base_search_provider import BaseSearchProvider, response_to_dict
from search_providers.factory import build_search_provider
from tools.base_tool import BaseTool
from weather_providers.base_weather_provider import BaseWeatherProvider, weather_to_dict
from weather_providers.factory import build_weather_provider


class SearchTool(BaseTool):
    name = "search_tool"
    description = "Search external sources through a configurable SearchProvider."

    def __init__(
        self,
        search_provider: BaseSearchProvider | None = None,
        weather_provider: BaseWeatherProvider | None = None,
    ):
        self.search_provider = search_provider if search_provider is not None else build_search_provider()
        self.weather_provider = (
            weather_provider if weather_provider is not None else build_weather_provider()
        )

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        query = self._query_from_params(params)
        if self._is_weather_query(query):
            return self._weather_result(query)

        max_results = int(params.get("max_results") or 5)
        response = self.search_provider.search(query, max_results=max_results)
        payload = response_to_dict(response)
        search_results = payload["results"]
        sources = [
            item["url"]
            for item in search_results
            if item.get("url")
        ]
        return {
            "message": f"找到 {len(search_results)} 条搜索结果",
            "query": payload["query"],
            "search_results": search_results,
            "sources": sources,
            "provider": payload["provider"],
        }

    def _query_from_params(self, params: dict[str, Any]) -> str:
        explicit = str(params.get("query") or "").strip()
        if explicit:
            return explicit
        text = str(params.get("user_input") or params.get("goal") or "").strip()
        text = re.sub(
            r"^(?:请|帮我|请帮我|麻烦)?(?:联网|上网|网络|互联网|在线)?(?:搜索|调研|查找|研究|查询)",
            "",
            text,
        ).strip()
        return text or "UTA Agent"

    def _is_weather_query(self, query: str) -> bool:
        weather_markers = (
            "天气",
            "气温",
            "温度",
            "降雨",
            "降水",
            "下雨",
            "下雪",
            "风力",
            "风速",
            "湿度",
            "冷不冷",
            "热不热",
        )
        return any(marker in query for marker in weather_markers)

    def _weather_result(self, query: str) -> dict[str, Any]:
        city = self._weather_city_from_query(query)
        weather = weather_to_dict(self.weather_provider.current_weather(city))
        display_city = str(weather.get("city") or city)
        source_url = str(weather.get("source_url") or "")
        provider = str(weather.get("provider") or getattr(self.weather_provider, "provider_name", "weather"))
        snippet = self._weather_snippet(weather)
        search_results = [
            {
                "title": f"{display_city} 今日天气",
                "url": source_url,
                "snippet": snippet,
                "source": provider,
            }
        ]
        sources = [source_url] if source_url else []
        return {
            "message": f"获取到 {display_city} 当前天气",
            "query": query,
            "weather_result": weather,
            "search_results": search_results,
            "sources": sources,
            "provider": provider,
        }

    def _weather_city_from_query(self, query: str) -> str:
        text = query.strip()
        text = re.sub(
            r"(今日|今天|现在|当前|实时|马上|此刻|的|天气状况|天气情况|天气预报|天气|气温|温度|降雨|降水|下雨|下雪|风力|风速|湿度|情况|状况|怎么样|如何|查询|搜索)",
            "",
            text,
        )
        text = re.sub(r"\s+", "", text).strip(" ：:，,。?？")
        return text or query.strip() or "北京"

    def _weather_snippet(self, weather: dict[str, Any]) -> str:
        city = str(weather.get("city") or "当前城市")
        weather_text = str(weather.get("weather_text") or "未知天气")
        parts = [f"{city}当前{weather_text}"]
        temperature = self._format_number(weather.get("temperature"))
        if temperature:
            parts.append(f"气温 {temperature}℃")
        apparent = self._format_number(weather.get("apparent_temperature"))
        if apparent:
            parts.append(f"体感 {apparent}℃")
        humidity = self._format_number(weather.get("relative_humidity"))
        if humidity:
            parts.append(f"湿度 {humidity}%")
        precipitation = self._format_number(weather.get("precipitation"))
        if precipitation:
            parts.append(f"降水量 {precipitation} mm")
        wind_speed = self._format_number(weather.get("wind_speed"))
        if wind_speed:
            parts.append(f"风速 {wind_speed} km/h")
        return "，".join(parts) + "。"

    def _format_number(self, value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
