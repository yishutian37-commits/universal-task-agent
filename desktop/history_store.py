from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, output_root: Path | str):
        self.output_root = Path(output_root)
        self.states_dir = self.output_root / "states"
        self.logs_dir = self.output_root / "logs"

    def list_runs(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        for path in self._state_paths():
            state = self._read_state(path)
            if not isinstance(state, dict):
                continue
            task_id = self._task_id_from_path(path)
            runs.append(self._summary(task_id, path, state))

        runs.sort(key=lambda item: item["modified_at"], reverse=True)
        return {"ok": True, "runs": runs}

    def get_run(self, task_id: str) -> dict[str, Any]:
        path = self._state_path_for_task(task_id)
        if path is None or not path.exists():
            return {"ok": False, "error": "任务不存在"}

        state = self._read_state(path)
        if not isinstance(state, dict):
            return {"ok": False, "error": "state JSON 无效"}

        log_path = self._log_path_for_task(task_id)
        log = self._read_log(log_path) if log_path is not None else ""
        return {
            "ok": True,
            "task_id": task_id,
            "state": state,
            "log": log,
            "final_output": str(state.get("final_output") or ""),
        }

    def _state_paths(self) -> list[Path]:
        if not self.states_dir.exists():
            return []
        return sorted(
            path
            for path in self.states_dir.glob("*_state.json")
            if self._is_contained(path, self.states_dir)
        )

    def _state_path_for_task(self, task_id: str) -> Path | None:
        if not task_id or "/" in task_id or "\\" in task_id:
            return None
        candidate = self.states_dir / f"{task_id}_state.json"
        return candidate if self._is_contained(candidate, self.states_dir) else None

    def _log_path_for_task(self, task_id: str) -> Path | None:
        if not task_id or "/" in task_id or "\\" in task_id:
            return None
        candidate = self.logs_dir / f"{task_id}.log"
        if not candidate.exists():
            return candidate
        return candidate if self._is_contained(candidate, self.logs_dir) else None

    def _is_contained(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    def _task_id_from_path(self, path: Path) -> str:
        return path.name.removesuffix("_state.json")

    def _read_state(self, path: Path) -> dict[str, Any] | None:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _read_log(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def _summary(self, task_id: str, path: Path, state: dict[str, Any]) -> dict[str, Any]:
        final_output = str(state.get("final_output") or "")
        intent = str(state.get("intent") or "")
        preview = self._preview(final_output or intent)
        return {
            "task_id": task_id,
            "status": str(state.get("status") or "unknown"),
            "task_type": str(state.get("task_type") or "unknown"),
            "intent": intent,
            "updated_at": str(state.get("updated_at") or ""),
            "modified_at": self._modified_at(path),
            "preview": preview,
        }

    def _preview(self, text: str, limit: int = 120) -> str:
        normalized = " ".join(str(text).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    def _modified_at(self, path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
