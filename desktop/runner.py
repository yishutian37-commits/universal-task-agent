from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from desktop.paths import resource_path, uta_home
from desktop.settings_store import SettingsStore
from tools.registry import build_tool_registry


def _generate_task_id() -> str:
    return "task_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


class TaskCancelledError(Exception):
    """用户取消任务时，在 on_progress 检查点抛出。

    继承 Exception（非 BaseException），确保被 _run 的异常处理覆盖。
    从 _emit_progress 抛出 → 沿 loop/run_task 冒泡（两者均无 try/except）→ 回到 _run。
    """

    def __init__(self, task_id: str = "") -> None:
        super().__init__(f"task cancelled: {task_id}" if task_id else "task cancelled")
        self.task_id = task_id


class TaskRunner:
    def __init__(
        self,
        window=None,
        memory_root: Path | str | None = None,
        settings_store: SettingsStore | None = None,
        run_task_func: Callable[..., Any] | None = None,
    ):
        home = uta_home()
        self.window = window
        self.memory_root = Path(memory_root) if memory_root is not None else home / "memory"
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.run_task_func = run_task_func
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running_task_id: str | None = None
        self._cancel_event = threading.Event()
        self._results: dict[str, dict[str, Any]] = {}

    def bind_window(self, window) -> None:
        self.window = window

    def start(self, user_input: str) -> str:
        with self._lock:
            if self._running_task_id is not None:
                raise RuntimeError("已有任务正在运行")
            task_id = _generate_task_id()
            self._running_task_id = task_id
            self._cancel_event.clear()
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
        with self._lock:
            if self._running_task_id != task_id:
                return {"ok": False, "error": "任务不在运行中"}
            self._cancel_event.set()
        return {"ok": True, "task_id": task_id, "status": "cancelling"}

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
                task_id=task_id,
                tool_registry=build_tool_registry(
                    project_root=resource_path("."),
                    skills_root=resource_path("skills"),
                    memory_root=self.memory_root,
                ),
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
        except TaskCancelledError:
            with self._lock:
                self._results[task_id].update(
                    {
                        "status": "cancelled",
                        "final_output": None,
                    }
                )
            self._emit_progress_safely(
                {"type": "cancelled", "task_id": task_id, "data": {}}
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
        # 取消检查点：loop 在每次 LLM 调用前后都会调 on_progress（即此方法），
        # 在此检查取消标志能在两次 LLM 调用之间及时中断。
        if self._cancel_event.is_set():
            raise TaskCancelledError(task_id=str(event.get("task_id", "")))

        self._emit_progress_safely(event)

    def _emit_progress_safely(self, event: dict[str, Any]) -> None:
        """推送事件但不检查取消标志（用于 cancelled/error 事件自身）。"""
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
