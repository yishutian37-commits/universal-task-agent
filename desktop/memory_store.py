from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from desktop.memory_compression import default_long_term_memory, merge_long_term_memory


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
            long_term_memory = self.load_long_term_memory()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        long_term_facts = long_term_memory.get("facts") if isinstance(long_term_memory.get("facts"), list) else []
        return {
            "ok": True,
            "task_history": task_history,
            "lessons": lessons,
            "negative_rules": negative_rules,
            "skill_candidates": skill_candidates,
            "user_profile": user_profile,
            "long_term_memory": long_term_memory,
            "long_term_facts": long_term_facts,
            "counts": {
                "tasks": len(task_history),
                "lessons": len(lessons),
                "negative_rules": len(negative_rules),
                "skill_candidates": len(skill_candidates),
                "long_term_facts": len(long_term_facts),
            },
        }

    def load_long_term_memory(self) -> dict[str, Any]:
        path = self.memory_root / "long_term_memory.json"
        if not path.exists():
            return default_long_term_memory()
        payload = self._read_payload("long_term_memory.json")
        return merge_long_term_memory(payload, [], conversation_id="")

    def save_long_term_memory(self, memory: dict[str, Any]) -> None:
        self._write_payload("long_term_memory.json", memory)

    def merge_long_term_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        conversation_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        try:
            memory = self.load_long_term_memory()
            merged = merge_long_term_memory(memory, candidates, conversation_id=conversation_id, now=now)
            self.save_long_term_memory(merged)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "long_term_memory": merged}

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

    def _write_payload(self, filename: str, payload: dict[str, Any]) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        path = self.memory_root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
