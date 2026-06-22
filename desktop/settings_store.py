from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from desktop.paths import uta_home


DEFAULT_SETTINGS = {
    "llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
    "llm_model": "mimo-v2.5-pro",
    "llm_api_key": "",
    "llm_ssl_verify": True,
}


class SettingsStore:
    def __init__(self, config_path: Path | str | None = None):
        self.config_path = Path(config_path) if config_path is not None else uta_home() / "config.json"

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return dict(DEFAULT_SETTINGS)

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return dict(DEFAULT_SETTINGS)

        if not isinstance(payload, dict):
            return dict(DEFAULT_SETTINGS)

        settings = dict(DEFAULT_SETTINGS)
        for key in DEFAULT_SETTINGS:
            if key in payload:
                settings[key] = payload[key]
        settings["llm_ssl_verify"] = self._to_bool(settings["llm_ssl_verify"])
        return settings

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.load()

        for key in ("llm_base_url", "llm_model"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                settings[key] = value.strip()

        if payload.get("clear_api_key") is True:
            settings["llm_api_key"] = ""
        else:
            api_key = payload.get("llm_api_key")
            if isinstance(api_key, str) and api_key.strip():
                settings["llm_api_key"] = api_key.strip()

        if "llm_ssl_verify" in payload:
            settings["llm_ssl_verify"] = self._to_bool(payload["llm_ssl_verify"])

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return settings

    def public_settings(self) -> dict[str, Any]:
        settings = self.load()
        return {
            "llm_base_url": settings["llm_base_url"],
            "llm_model": settings["llm_model"],
            "llm_ssl_verify": settings["llm_ssl_verify"],
            "has_api_key": bool(settings["llm_api_key"]),
        }

    def apply_to_environment(self) -> None:
        settings = self.load()
        os.environ["LLM_API_KEY"] = str(settings["llm_api_key"])
        os.environ["LLM_BASE_URL"] = str(settings["llm_base_url"])
        os.environ["LLM_MODEL"] = str(settings["llm_model"])
        os.environ["LLM_SSL_VERIFY"] = "1" if settings["llm_ssl_verify"] else "0"

        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off"}
        return bool(value)
