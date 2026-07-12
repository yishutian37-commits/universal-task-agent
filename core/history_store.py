from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HistoryStore:
    """从 JSON Memory 的 task_history.json 读取历史任务。

    早期版本读 outputs/states/*_state.json 与 outputs/logs/*.log（学习框架产物）。
    现在统一读 memory/task_history.json——这是跨任务持久层的正牌位置，
    state.json/log 落盘已移除。
    """

    def __init__(self, memory_root: Path | str):
        self.memory_root = Path(memory_root)
        self.history_path = self.memory_root / "task_history.json"

    def list_runs(self) -> dict[str, Any]:
        tasks = self._read_tasks()
        if tasks is None:
            return {"ok": False, "error": "历史记录不可读"}

        # 最近优先；task_history.json 是按写入时间追加的，倒序即新到旧。
        ordered = list(reversed(tasks))
        runs = [self._summary(task) for task in ordered if isinstance(task, dict)]
        return {"ok": True, "runs": runs}

    def get_run(self, task_id: str) -> dict[str, Any]:
        if not self._is_safe_task_id(task_id):
            return {"ok": False, "error": "任务不存在"}

        tasks = self._read_tasks()
        if tasks is None:
            return {"ok": False, "error": "历史记录不可读"}

        for task in tasks:
            if isinstance(task, dict) and str(task.get("task_id") or "") == task_id:
                return self._run_payload(task_id, task)

        for task in self._read_archived_tasks():
            if isinstance(task, dict) and str(task.get("task_id") or "") == task_id:
                return self._run_payload(task_id, task)

        return {"ok": False, "error": "任务不存在"}

    def _read_tasks(self) -> list[dict[str, Any]] | None:
        if not self.history_path.exists():
            return []
        try:
            parsed = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        tasks = parsed.get("tasks")
        if not isinstance(tasks, list):
            return []
        return tasks

    def _read_archived_tasks(self) -> list[dict[str, Any]]:
        archive_root = self.memory_root / "archives"
        if not archive_root.exists() or archive_root.is_symlink():
            return []

        tasks: list[dict[str, Any]] = []
        for path in sorted(archive_root.glob("task_history_*.json"), reverse=True):
            if path.is_symlink():
                continue
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(parsed, dict):
                continue
            archived_tasks = parsed.get("tasks")
            if isinstance(archived_tasks, list):
                tasks.extend(task for task in archived_tasks if isinstance(task, dict))
        return tasks

    def _run_payload(self, task_id: str, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "task_id": task_id,
            "state": self._state_view(task),
            "final_output": str(task.get("final_output") or ""),
        }

    def _summary(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": str(task.get("task_id") or ""),
            "status": str(task.get("status") or "unknown"),
            "task_type": str(task.get("task_type") or "unknown"),
            "intent": str(task.get("intent") or ""),
            "updated_at": str(task.get("updated_at") or ""),
            "modified_at": str(task.get("updated_at") or ""),
            "preview": self._preview(str(task.get("final_output_preview") or task.get("intent") or "")),
        }

    def _state_view(self, task: dict[str, Any]) -> dict[str, Any]:
        """给前端历史详情页的字段视图（不是完整 AgentState，而是记录字段的子集）。"""
        return {
            "task_id": str(task.get("task_id") or ""),
            "user_input": str(task.get("user_input") or ""),
            "task_type": str(task.get("task_type") or "unknown"),
            "intent": str(task.get("intent") or ""),
            "status": str(task.get("status") or "unknown"),
            "updated_at": str(task.get("updated_at") or ""),
            "result_count": int(task.get("result_count") or 0),
            "check_count": int(task.get("check_count") or 0),
            "feedback_count": int(task.get("feedback_count") or 0),
            "final_output": str(task.get("final_output") or ""),
        }

    def _is_safe_task_id(self, task_id: str) -> bool:
        # task_id 直接做字符串比较，不拼路径，所以路径穿越不再可能；
        # 但仍拒绝空值与含分隔符的输入，保持防御性。
        if not task_id or "/" in task_id or "\\" in task_id:
            return False
        return True

    def _preview(self, text: str, limit: int = 120) -> str:
        normalized = " ".join(str(text).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."
