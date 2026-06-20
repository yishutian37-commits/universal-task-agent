from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.state import AgentState
from memory_providers.base_memory_provider import BaseMemoryProvider


DEFAULT_FILES = {
    "user_profile": ("user_profile.json", {"version": 1, "profile": {}, "updated_at": None}),
    "task_history": ("task_history.json", {"version": 1, "tasks": []}),
    "lessons": ("lessons.json", {"version": 1, "lessons": []}),
    "negative_rules": ("negative_rules.json", {"version": 1, "negative_rules": []}),
    "skill_candidates": ("skill_candidates.json", {"version": 1, "candidates": []}),
}


class JsonMemoryProvider(BaseMemoryProvider):
    def __init__(self, memory_root: Path | str = "memory"):
        self.memory_root = Path(memory_root)
        self.ensure_store()

    def ensure_store(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        for _key, (filename, default_payload) in DEFAULT_FILES.items():
            path = self.memory_root / filename
            if not path.exists():
                self._write_json(path, default_payload)

    def load_context(self) -> dict[str, Any]:
        self.ensure_store()
        return {
            key: self._read_json(self.memory_root / filename)
            for key, (filename, _default_payload) in DEFAULT_FILES.items()
        }

    def save_task(self, state: AgentState) -> None:
        self.ensure_store()

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
