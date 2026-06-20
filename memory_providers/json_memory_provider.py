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
        self._save_task_history(state)
        if state.status == "completed":
            self._save_lesson(state)

    def _save_task_history(self, state: AgentState) -> None:
        path = self.memory_root / "task_history.json"
        payload = self._read_json(path)
        record = {
            "task_id": state.task_id,
            "task_type": state.task_type,
            "intent": state.intent,
            "status": state.status,
            "final_output_preview": self._preview(state.final_output),
            "result_count": len(state.results),
            "check_count": len(state.checks),
            "feedback_count": len(state.feedbacks),
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }
        payload["tasks"] = self._upsert_by_key(payload["tasks"], "task_id", record)
        self._write_json(path, payload)

    def _save_lesson(self, state: AgentState) -> None:
        path = self.memory_root / "lessons.json"
        payload = self._read_json(path)
        record = {
            "lesson_id": f"lesson_{state.task_id}",
            "task_id": state.task_id,
            "task_type": state.task_type,
            "content": (
                f"{state.task_type} 任务已成功跑通，可复用流程："
                "读取输入 -> 处理内容 -> 生成报告。"
            ),
            "source": "completed_task",
            "created_at": state.updated_at,
        }
        payload["lessons"] = self._upsert_by_key(payload["lessons"], "lesson_id", record)
        self._write_json(path, payload)

    def _upsert_by_key(
        self,
        records: list[dict[str, Any]],
        key: str,
        record: dict[str, Any],
    ) -> list[dict[str, Any]]:
        for index, existing in enumerate(records):
            if existing.get(key) == record.get(key):
                updated = list(records)
                updated[index] = record
                return updated
        return [*records, record]

    def _preview(self, value: str | None, limit: int = 300) -> str:
        if value is None:
            return ""
        return str(value)[:limit]

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
