from __future__ import annotations

from typing import Any

from desktop.history_store import HistoryStore
from desktop.memory_store import MemoryStore
from desktop.paths import resource_path, uta_home
from desktop.runner import TaskRunner
from desktop.settings_store import SettingsStore


class DesktopAPI:
    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        runner: TaskRunner | None = None,
        history_store: HistoryStore | None = None,
        memory_store: MemoryStore | None = None,
    ):
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.runner = runner if runner is not None else TaskRunner(settings_store=self.settings_store)
        self.history_store = history_store if history_store is not None else HistoryStore(uta_home() / "outputs")
        self.memory_store = memory_store if memory_store is not None else MemoryStore(uta_home() / "memory")

    def bind_window(self, window) -> None:
        if hasattr(self.runner, "bind_window"):
            self.runner.bind_window(window)

    def get_settings(self) -> dict[str, Any]:
        return self.settings_store.public_settings()

    def save_settings(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            self.settings_store.save(payload or {})
            self.settings_store.apply_to_environment()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def load_example(self, category: str = "summarize") -> dict[str, Any]:
        if category in {"summarize", "summary"}:
            example_path = resource_path("examples", "summarize_example.txt")
            content = example_path.read_text(encoding="utf-8") if example_path.exists() else ""
            return {
                "ok": True,
                "title": "文本总结示例",
                "input": f"帮我总结一段文本：{content}".strip(),
            }

        if category in {"data", "table", "data_analysis"}:
            table_path = resource_path("examples", "orders.csv")
            return {
                "ok": True,
                "title": "表格分析示例",
                "input": f"分析 {table_path}，输出字段说明、基础统计、异常数据、分类汇总和后续建议。",
            }

        return {"ok": False, "error": f"未知示例类型：{category}"}

    def run_task(self, user_input: str) -> dict[str, Any]:
        text = str(user_input or "").strip()
        if not text:
            return {"ok": False, "error": "请输入任务内容"}

        if not self.settings_store.public_settings()["has_api_key"]:
            return {"ok": False, "error": "请先配置 API Key"}

        try:
            task_id = self.runner.start(text)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "task_id": task_id}

    def list_runs(self) -> dict[str, Any]:
        try:
            return self.history_store.list_runs()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_run(self, task_id: str) -> dict[str, Any]:
        try:
            return self.history_store.get_run(str(task_id or ""))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_memory_overview(self) -> dict[str, Any]:
        try:
            return self.memory_store.overview()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_result(self, task_id: str) -> dict[str, Any]:
        return self.runner.get_result(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self.runner.cancel(task_id)
