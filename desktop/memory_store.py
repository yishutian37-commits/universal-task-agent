from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, memory_root: Path | str):
        self.memory_root = Path(memory_root)

    def overview(self) -> dict[str, Any]:
        try:
            task_history = self._list_from_file("task_history.json", "tasks")
            lessons = self._list_from_file("lessons.json", "lessons")
            negative_rules = self._list_from_file("negative_rules.json", "negative_rules")
            skill_candidates = self._list_from_file("skill_candidates.json", "candidates")
            user_profile = self._dict_from_file("user_profile.json", "profile")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "task_history": task_history,
            "lessons": lessons,
            "negative_rules": negative_rules,
            "skill_candidates": skill_candidates,
            "user_profile": user_profile,
            "counts": {
                "tasks": len(task_history),
                "lessons": len(lessons),
                "negative_rules": len(negative_rules),
                "skill_candidates": len(skill_candidates),
            },
        }

    def _list_from_file(self, filename: str, key: str) -> list[dict[str, Any]]:
        payload = self._read_payload(filename)
        value = payload.get(key, [])
        return value if isinstance(value, list) else []

    def _dict_from_file(self, filename: str, key: str) -> dict[str, Any]:
        payload = self._read_payload(filename)
        value = payload.get(key, {})
        return value if isinstance(value, dict) else {}

    def _read_payload(self, filename: str) -> dict[str, Any]:
        path = self.memory_root / filename
        if not path.exists():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{filename} 无法读取或 JSON 无效") from exc
        return parsed if isinstance(parsed, dict) else {}
