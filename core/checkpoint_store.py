from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.state import AgentState


class CheckpointStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def save(self, state: AgentState) -> Path:
        path = self._path_for(state.task_id)
        if path is None:
            raise ValueError("任务 ID 无效")
        self.root.mkdir(parents=True, exist_ok=True)
        payload = state.to_dict()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
        return path

    def load(self, task_id: str) -> AgentState | None:
        path = self._path_for(task_id)
        if path is None or not path.exists() or path.is_symlink():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return AgentState.from_dict(payload)

    def list_unfinished(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        items = []
        for path in self.root.glob("task_*.json"):
            state = self.load(path.stem)
            if state is None or state.status in {"completed", "failed", "cancelled"}:
                continue
            items.append(
                {
                    "task_id": state.task_id,
                    "status": state.status,
                    "current_step_id": state.current_step_id,
                    "updated_at": state.updated_at,
                    "preview": state.user_input[:120],
                }
            )
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return items

    def _path_for(self, task_id: str) -> Path | None:
        value = str(task_id or "")
        if not re.fullmatch(r"task_[A-Za-z0-9_.-]+", value):
            return None
        return self.root / f"{value}.json"
