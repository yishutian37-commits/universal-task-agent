from __future__ import annotations

from typing import Any

from core.history_store import HistoryStore
from tools.base_tool import BaseTool


class HistoryTool(BaseTool):
    name = "history_tool"
    description = "List previous UTA tasks from JSON Memory task history."

    def __init__(
        self,
        memory_root: str = "memory",
        limit: int = 20,
    ):
        self.memory_root = memory_root
        self.limit = limit

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name, params
        tasks = self._memory_history_tasks()
        markdown = self._format_report(tasks)
        return {
            "message": markdown,
            "history_markdown": markdown,
            "history_query": True,
            "source": "memory",
            "tasks": tasks,
        }

    def _memory_history_tasks(self) -> list[dict[str, Any]]:
        store = HistoryStore(self.memory_root)
        listed = store.list_runs()
        runs = listed.get("runs", []) if listed.get("ok") else []
        tasks: list[dict[str, Any]] = []
        for run in runs:
            if len(tasks) >= self.limit:
                break
            task_id = str(run.get("task_id") or "")
            detail = store.get_run(task_id)
            state = detail.get("state", {}) if detail.get("ok") else {}
            if not isinstance(state, dict):
                state = {}
            user_input = str(state.get("user_input") or "").strip()
            intent = str(state.get("intent") or run.get("intent") or "").strip()
            tasks.append(
                {
                    "task_id": task_id,
                    "user_input": user_input,
                    "task_type": str(state.get("task_type") or run.get("task_type") or "unknown"),
                    "intent": intent,
                    "status": str(state.get("status") or run.get("status") or "unknown"),
                    "updated_at": str(state.get("updated_at") or run.get("updated_at") or ""),
                    "preview": str(run.get("preview") or ""),
                }
            )
        return tasks

    def _format_report(self, tasks: list[dict[str, Any]]) -> str:
        lines = [
            "## 历史任务",
            "",
        ]
        if not tasks:
            lines.append("暂无历史任务记录。")
            return "\n".join(lines)

        lines.append(f"以下是最近 {len(tasks)} 条历史任务记录，来源：memory。")
        lines.append("")
        for index, task in enumerate(tasks, start=1):
            user_input = task.get("user_input") or task.get("intent") or task.get("preview") or "未记录原始输入"
            lines.append(f"{index}. {user_input}")
            lines.append(
                f"   - task_id：{task.get('task_id') or 'unknown'}；"
                f"类型：{task.get('task_type') or 'unknown'}；"
                f"状态：{task.get('status') or 'unknown'}"
            )
            if task.get("updated_at"):
                lines.append(f"   - 时间：{task['updated_at']}")
        return "\n".join(lines)
