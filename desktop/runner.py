from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from desktop.paths import resource_path, uta_home
from desktop.settings_store import SettingsStore


def _generate_task_id() -> str:
    return "task_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def build_tool_registry() -> dict[str, Any]:
    from tools.code_tool import CodeTool
    from tools.file_tool import FileTool
    from tools.mock_tool import MockTool
    from tools.report_tool import ReportTool
    from tools.search_tool import SearchTool
    from tools.table_tool import TableTool
    from tools.text_tool import TextTool

    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(resource_path(".")),
        "file_tool": FileTool(),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


class TaskRunner:
    def __init__(
        self,
        window=None,
        output_root: Path | str | None = None,
        memory_root: Path | str | None = None,
        settings_store: SettingsStore | None = None,
        run_task_func: Callable[..., Any] | None = None,
    ):
        home = uta_home()
        self.window = window
        self.output_root = Path(output_root) if output_root is not None else home / "outputs"
        self.memory_root = Path(memory_root) if memory_root is not None else home / "memory"
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.run_task_func = run_task_func
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running_task_id: str | None = None
        self._results: dict[str, dict[str, Any]] = {}

    def bind_window(self, window) -> None:
        self.window = window

    def start(self, user_input: str) -> str:
        with self._lock:
            if self._running_task_id is not None:
                raise RuntimeError("已有任务正在运行")
            task_id = _generate_task_id()
            self._running_task_id = task_id
            self._results[task_id] = {
                "task_id": task_id,
                "status": "running",
                "final_output": None,
                "state": None,
                "events": [],
                "error": None,
            }

        thread = threading.Thread(
            target=self._run,
            args=(task_id, user_input),
            name=f"uta-desktop-{task_id}",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return task_id

    def get_result(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            result = self._results.get(task_id)
            if result is None:
                return {"task_id": task_id, "status": "not_found", "error": "任务不存在"}
            return dict(result)

    def cancel(self, task_id: str) -> dict[str, Any]:
        return {"ok": False, "task_id": task_id, "error": "当前版本暂不支持取消"}

    def wait_for_task(self, task_id: str, timeout: float | None = None) -> dict[str, Any]:
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        return self.get_result(task_id)

    def _run(self, task_id: str, user_input: str) -> None:
        try:
            self.settings_store.apply_to_environment()
            from core.skill_loader import SkillLoader
            from main import run_task
            from memory_providers.json_memory_provider import JsonMemoryProvider

            run_task_func = self.run_task_func if self.run_task_func is not None else run_task
            state = run_task_func(
                user_input,
                output_root=self.output_root,
                task_id=task_id,
                tool_registry=build_tool_registry(),
                memory_provider=JsonMemoryProvider(self.memory_root),
                skill_loader=SkillLoader(resource_path("skills")),
                on_progress=self._emit_progress,
            )
            with self._lock:
                self._results[task_id].update(
                    {
                        "status": state.status,
                        "final_output": state.final_output,
                        "state": state.to_dict(),
                    }
                )
        except Exception as exc:
            event = {
                "type": "error",
                "task_id": task_id,
                "data": {"message": str(exc)},
            }
            self._emit_progress(event)
            with self._lock:
                self._results[task_id].update(
                    {
                        "status": "failed",
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                )
        finally:
            with self._lock:
                if self._running_task_id == task_id:
                    self._running_task_id = None

    def _emit_progress(self, event: dict[str, Any]) -> None:
        task_id = str(event.get("task_id", ""))
        with self._lock:
            if task_id in self._results:
                self._results[task_id]["events"].append(event)

        if self.window is None:
            return

        payload = json.dumps(event, ensure_ascii=False)
        try:
            self.window.evaluate_js(f"window.onProgress && window.onProgress({payload});")
        except Exception:
            return
