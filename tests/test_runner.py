"""TaskRunner 取消机制测试。

验证基于 on_progress 检查点的软取消：
- cancel 设置取消标志 → 下一个 _emit_progress 检查点抛 TaskCancelledError
- _run 捕获后把结果记成 status=cancelled
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from core.state import AgentState
from desktop.runner import TaskCancelledError, TaskRunner


class SlowTaskSimulator:
    """模拟 main.run_task：在每个 on_progress 回调间 sleep，制造可取消窗口。"""

    def __init__(self, delay: float = 0.05, steps: int = 50):
        self.delay = delay
        self.steps = steps

    def __call__(self, user_input, **kwargs):
        on_progress = kwargs.get("on_progress")
        from core.state import AgentState

        state = AgentState(task_id="task_test", user_input=user_input)

        # 模拟 loop 的多次 on_progress 调用（每次 LLM 调用前后都有）
        for i in range(self.steps):
            if on_progress is not None:
                on_progress(
                    {
                        "type": "step_started",
                        "task_id": "task_test",
                        "data": {"step_id": i},
                    }
                )
            time.sleep(self.delay)  # 模拟 LLM 阻塞

        state.status = "completed"
        state.final_output = "done"
        return state


def _make_runner(run_task_func=None) -> TaskRunner:
    return TaskRunner(run_task_func=run_task_func or SlowTaskSimulator())


class FakeCheckpointStore:
    def __init__(self, state=None):
        self.state = state
        self.loaded_task_ids = []

    def load(self, task_id):
        self.loaded_task_ids.append(task_id)
        return self.state

    def save(self, state):
        self.state = state


class ResumeTaskSimulator:
    def __init__(self):
        self.calls = []

    def __call__(self, user_input, **kwargs):
        self.calls.append((user_input, kwargs))
        state = AgentState(
            task_id=kwargs["task_id"],
            user_input=kwargs.get("display_user_input") or user_input,
            execution_input=user_input,
            status="completed",
        )
        state.final_output = "resumed"
        return state


class CapturingRegistryTask:
    def __init__(self):
        self.kwargs = None

    def __call__(self, user_input, **kwargs):
        self.kwargs = kwargs
        state = AgentState(task_id=kwargs["task_id"], user_input=user_input, status="completed")
        state.final_output = "done"
        return state


class DangerousSettingsStore:
    def __init__(self, workspace_path=""):
        self.workspace_path = workspace_path

    def apply_to_environment(self):
        pass

    def load(self):
        return {
            "dangerous_tools_enabled": True,
            "desktop_access_enabled": True,
            "workspace_path": self.workspace_path,
        }


def test_cancel_running_task_sets_cancelled_status():
    runner = _make_runner(SlowTaskSimulator(delay=0.05, steps=50))

    task_id = runner.start("测试任务")
    time.sleep(0.1)  # 等任务进入循环

    result = runner.cancel(task_id)

    assert result["ok"] is True
    assert result["status"] == "cancelling"

    runner.wait_for_task(task_id, timeout=5)
    final = runner.get_result(task_id)

    assert final["status"] == "cancelled"
    assert final["final_output"] is None


def test_resume_task_loads_checkpoint_and_runs_with_resume_flag():
    loaded_state = AgentState(
        task_id="task_resume",
        user_input="帮我总结",
        execution_input="带上下文的输入",
        status="running",
    )
    checkpoint_store = FakeCheckpointStore(loaded_state)
    simulator = ResumeTaskSimulator()
    runner = TaskRunner(run_task_func=simulator, checkpoint_store=checkpoint_store)

    result = runner.resume("task_resume")
    runner.wait_for_task("task_resume", timeout=5)
    final = runner.get_result("task_resume")

    assert result["ok"] is True
    assert result["task_id"] == "task_resume"
    assert checkpoint_store.loaded_task_ids == ["task_resume"]
    assert simulator.calls[0][0] == "带上下文的输入"
    assert simulator.calls[0][1]["display_user_input"] == "帮我总结"
    assert simulator.calls[0][1]["resume_from_checkpoint"] is True
    assert final["status"] == "completed"
    assert final["final_output"] == "resumed"


def test_resume_task_uses_checkpoint_workspace_instead_of_current_setting(monkeypatch, tmp_path):
    original_workspace = tmp_path / "original"
    current_workspace = tmp_path / "current"
    original_workspace.mkdir()
    current_workspace.mkdir()
    loaded_state = AgentState(
        task_id="task_resume_workspace",
        user_input="读取 README.md",
        execution_input="读取 README.md",
        conversation_id="conv_20260708_120000_000001",
        workspace_path=str(original_workspace),
        status="running",
    )
    captured = {}

    def fake_build_tool_registry(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr("desktop.runner.build_tool_registry", fake_build_tool_registry)
    runner = TaskRunner(
        run_task_func=ResumeTaskSimulator(),
        checkpoint_store=FakeCheckpointStore(loaded_state),
        settings_store=DangerousSettingsStore(str(current_workspace)),
    )

    result = runner.resume("task_resume_workspace")
    runner.wait_for_task("task_resume_workspace", timeout=5)

    assert result["ok"] is True
    assert result["conversation_id"] == "conv_20260708_120000_000001"
    assert result["workspace_path"] == str(original_workspace.resolve())
    assert captured["project_root"] == original_workspace.resolve()


def test_resume_task_rejects_missing_checkpoint_workspace(tmp_path):
    missing_workspace = tmp_path / "missing"
    loaded_state = AgentState(
        task_id="task_resume_missing_workspace",
        user_input="读取 README.md",
        workspace_path=str(missing_workspace),
        status="running",
    )
    runner = TaskRunner(
        run_task_func=ResumeTaskSimulator(),
        checkpoint_store=FakeCheckpointStore(loaded_state),
    )

    result = runner.resume("task_resume_missing_workspace")

    assert result["ok"] is False
    assert "原工作区不存在" in result["error"]


def test_get_resume_context_returns_checkpoint_ownership(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    loaded_state = AgentState(
        task_id="task_resume_context",
        user_input="读取 README.md",
        conversation_id="conv_20260708_120000_000001",
        workspace_path=str(workspace),
        status="running",
    )
    runner = TaskRunner(
        run_task_func=ResumeTaskSimulator(),
        checkpoint_store=FakeCheckpointStore(loaded_state),
    )

    result = runner.get_resume_context("task_resume_context")

    assert result == {
        "ok": True,
        "task_id": "task_resume_context",
        "conversation_id": "conv_20260708_120000_000001",
        "workspace_path": str(workspace.resolve()),
    }


def test_runner_passes_authorization_manager_to_tool_registry(monkeypatch, tmp_path):
    captured = {}

    def fake_build_tool_registry(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setenv("UTA_HOME", str(tmp_path / "uta"))
    monkeypatch.setattr("desktop.runner.build_tool_registry", fake_build_tool_registry)
    task = CapturingRegistryTask()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = TaskRunner(
        run_task_func=task,
        settings_store=DangerousSettingsStore(str(workspace)),
    )

    task_id = runner.start("执行 shell 命令 echo hello")
    runner.wait_for_task(task_id, timeout=5)

    assert captured["enable_dangerous_tools"] is True
    assert captured["authorization_manager"] is runner.authorization_manager
    assert captured["dangerous_allowed_roots"]
    assert captured["project_root"] == workspace.resolve()
    assert captured["dangerous_allowed_roots"][0] == workspace.resolve()
    assert Path.home() / "Desktop" in captured["dangerous_allowed_roots"]


def test_resume_task_reports_missing_checkpoint():
    runner = TaskRunner(run_task_func=ResumeTaskSimulator(), checkpoint_store=FakeCheckpointStore())

    result = runner.resume("task_missing")

    assert result["ok"] is False
    assert "checkpoint" in result["error"]


def test_cancel_task_not_running_returns_error():
    runner = _make_runner()

    result = runner.cancel("task_nonexistent")

    assert result["ok"] is False
    assert "不在运行中" in result["error"]


def test_cancel_flag_cleared_on_new_task():
    runner = _make_runner(SlowTaskSimulator(delay=0.01, steps=3))

    # 第一次任务：启动后立即取消
    task_id_1 = runner.start("第一次任务")
    runner.cancel(task_id_1)
    runner.wait_for_task(task_id_1, timeout=5)
    assert runner.get_result(task_id_1)["status"] == "cancelled"

    # 第二次任务：取消标志应已清除，能正常完成
    task_id_2 = runner.start("第二次任务")
    runner.wait_for_task(task_id_2, timeout=5)
    final = runner.get_result(task_id_2)

    assert final["status"] == "completed"
    assert final["final_output"] == "done"


def test_cancel_emits_cancelled_event():
    runner = _make_runner(SlowTaskSimulator(delay=0.05, steps=50))

    task_id = runner.start("测试事件")
    time.sleep(0.1)
    runner.cancel(task_id)
    runner.wait_for_task(task_id, timeout=5)

    result = runner.get_result(task_id)
    event_types = [e["type"] for e in result["events"]]

    assert "cancelled" in event_types


def test_task_cancelled_error_is_exception():
    # 确保 TaskCancelledError 继承 Exception（被 except Exception 覆盖）
    assert issubclass(TaskCancelledError, Exception)
    assert not issubclass(TaskCancelledError, BaseException) or issubclass(
        TaskCancelledError, Exception
    )
