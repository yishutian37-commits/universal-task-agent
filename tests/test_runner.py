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

from core.checkpoint_store import CheckpointStore
from core.loop import run_minimal_loop
from core.state import AgentState, Plan, PlanStep, ToolResult
from desktop.runner import TaskCancelledError, TaskRunner
from tools.base_tool import BaseTool


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


class EventEnvelopeTask:
    def __call__(self, user_input, **kwargs):
        kwargs["on_progress"](
            {
                "type": "step_started",
                "task_id": kwargs["task_id"],
                "data": {"step_id": 1},
            }
        )
        state = AgentState(task_id=kwargs["task_id"], user_input=user_input, status="completed")
        state.final_output = "done"
        return state


class InteractionTask:
    def __call__(self, user_input, **kwargs):
        manager = kwargs["interaction_manager"]
        decision = manager.request(
            "missing_info",
            {"title": "补充信息", "question": "请提供文件路径"},
            task_id=kwargs["task_id"],
        )
        state = AgentState(task_id=kwargs["task_id"], user_input=user_input)
        state.status = "completed" if decision.accepted else "cancelled"
        state.final_output = decision.response or None
        return state


class CountingResumeTool(BaseTool):
    name = "text_tool"
    description = "count resumed execution"

    def __init__(self):
        self.calls = 0

    def run(self, action_name, params):
        del action_name, params
        self.calls += 1
        return {"message": "恢复后完成", "call": self.calls}


class DurableInteractionTask:
    def __init__(self, tool):
        self.tool = tool

    def __call__(self, user_input, **kwargs):
        checkpoint_store = kwargs["checkpoint_store"]
        task_id = kwargs["task_id"]
        if kwargs.get("resume_from_checkpoint"):
            state = checkpoint_store.load(task_id)
            assert state is not None
        else:
            state = AgentState(
                task_id=task_id,
                user_input=kwargs.get("display_user_input") or user_input,
                execution_input=user_input,
                conversation_id=kwargs.get("conversation_id"),
                workspace_path=kwargs.get("workspace_path"),
                task_type="complex_task",
                status="running",
            )
            state.plan = Plan(
                plan_id=f"plan_{task_id}",
                task_id=task_id,
                status="running",
                requires_confirmation=True,
                steps=[
                    PlanStep(step_id=1, goal="已读取输入", status="completed"),
                    PlanStep(
                        step_id=2,
                        goal="生成最终结果",
                        status="pending",
                        tool_hint="text_tool",
                        action_hint="process",
                    ),
                ],
            )
            state.results.append(
                ToolResult(
                    True,
                    "file_tool",
                    "read",
                    {"message": "已读取"},
                    step_id=1,
                )
            )
            state.evidence["files"].append(
                {"path": "README.md", "step_id": 1, "source": "file_tool"}
            )
        return run_minimal_loop(
            state,
            tool_registry={"text_tool": self.tool},
            on_progress=kwargs.get("on_progress"),
            checkpoint_store=checkpoint_store,
            interaction_manager=kwargs.get("interaction_manager"),
        )


def _wait_for_runner_event(runner, task_id, event_type, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        event = next(
            (
                item
                for item in runner.get_result(task_id).get("events", [])
                if item["type"] == event_type
            ),
            None,
        )
        if event is not None:
            return event
        time.sleep(0.01)
    raise AssertionError(f"event not emitted: {event_type}")


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
    loaded_state.plan = Plan(
        plan_id="plan_task_resume_context",
        task_id=loaded_state.task_id,
        steps=[
            PlanStep(step_id=1, goal="读取文件", status="completed"),
            PlanStep(step_id=2, goal="生成报告", status="pending"),
        ],
    )
    loaded_state.evidence["files"].append(
        {"path": str(workspace / "README.md"), "source": "file_tool"}
    )
    loaded_state.pending_interaction = {
        "request_id": "interaction_resume_context",
        "task_id": loaded_state.task_id,
        "kind": "plan_confirmation",
        "payload": {"question": "请确认计划"},
        "status": "pending",
        "created_at": "2026-07-15T08:00:00",
    }
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
        "pending_interaction": loaded_state.pending_interaction,
        "completed_step_ids": [1],
        "evidence": loaded_state.evidence,
    }


def test_resume_result_keeps_checkpoint_identity_and_progress(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    loaded_state = AgentState(
        task_id="task_resume_progress",
        user_input="继续报告",
        conversation_id="conv_resume_progress",
        workspace_path=str(workspace),
        status="waiting_user",
    )
    loaded_state.plan = Plan(
        plan_id="plan_task_resume_progress",
        task_id=loaded_state.task_id,
        steps=[
            PlanStep(step_id=1, goal="读取数据", status="completed"),
            PlanStep(step_id=2, goal="确认报告", status="pending"),
        ],
    )
    loaded_state.evidence["artifacts"].append(
        {"path": str(workspace / "draft.md"), "step_id": 1}
    )
    loaded_state.pending_interaction = {
        "request_id": "interaction_resume_progress",
        "task_id": loaded_state.task_id,
        "kind": "plan_confirmation",
        "payload": {"question": "是否继续？"},
        "status": "pending",
        "created_at": "2026-07-15T08:10:00",
    }
    runner = TaskRunner(
        run_task_func=ResumeTaskSimulator(),
        checkpoint_store=FakeCheckpointStore(loaded_state),
    )

    result = runner.resume("task_resume_progress")
    runner.wait_for_task("task_resume_progress", timeout=5)

    assert result["task_id"] == "task_resume_progress"
    assert result["conversation_id"] == "conv_resume_progress"
    assert result["workspace_path"] == str(workspace.resolve())
    assert result["pending_interaction"] == loaded_state.pending_interaction
    assert result["completed_step_ids"] == [1]
    assert result["evidence"] == loaded_state.evidence


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


def test_runner_emits_interaction_request_and_accepts_response():
    runner = _make_runner(InteractionTask())

    task_id = runner.start("读取文件")
    deadline = time.time() + 2
    request_event = None
    while time.time() < deadline:
        events = runner.get_result(task_id)["events"]
        request_event = next(
            (event for event in events if event["type"] == "task_interaction_required"),
            None,
        )
        if request_event is not None:
            break
        time.sleep(0.01)

    assert request_event is not None
    response = runner.interaction_manager.respond(
        request_event["data"]["request_id"],
        accepted=True,
        response="/tmp/input.md",
    )
    runner.wait_for_task(task_id, timeout=2)

    assert response["ok"] is True
    assert runner.get_result(task_id)["status"] == "completed"
    assert runner.get_result(task_id)["final_output"] == "/tmp/input.md"


def test_cancel_wakes_task_waiting_for_user_interaction():
    runner = _make_runner(InteractionTask())
    task_id = runner.start("读取文件")
    deadline = time.time() + 2
    while time.time() < deadline:
        if any(
            event["type"] == "task_interaction_required"
            for event in runner.get_result(task_id)["events"]
        ):
            break
        time.sleep(0.01)

    cancelled = runner.cancel(task_id)
    runner.wait_for_task(task_id, timeout=2)

    assert cancelled["ok"] is True
    assert runner.get_result(task_id)["status"] == "cancelled"


def test_runner_replays_waiting_interaction_after_application_restart_without_duplicate_execution(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    primary_store = CheckpointStore(tmp_path / "primary-checkpoints")
    tool = CountingResumeTool()
    task = DurableInteractionTask(tool)
    first_runner = TaskRunner(
        run_task_func=task,
        checkpoint_store=primary_store,
        settings_store=DangerousSettingsStore(str(workspace)),
    )

    task_id = first_runner.start(
        "继续生成报告",
        conversation_id="conv_restart",
        workspace_path=str(workspace),
    )
    first_event = _wait_for_runner_event(
        first_runner,
        task_id,
        "task_interaction_required",
    )
    waiting_checkpoint = primary_store.load(task_id)
    assert waiting_checkpoint is not None
    assert waiting_checkpoint.status == "waiting_user"
    assert waiting_checkpoint.pending_interaction is not None
    request_id = waiting_checkpoint.pending_interaction["request_id"]
    assert first_event["data"]["request_id"] == request_id

    restart_store = CheckpointStore(tmp_path / "restart-checkpoints")
    restart_store.save(AgentState.from_dict(waiting_checkpoint.to_dict()))
    first_runner.interaction_manager.cancel_for_task(task_id)
    first_runner.wait_for_task(task_id, timeout=2)

    resumed_runner = TaskRunner(
        run_task_func=task,
        checkpoint_store=restart_store,
        settings_store=DangerousSettingsStore(str(workspace)),
    )
    resume_result = resumed_runner.resume(task_id)
    replayed_event = _wait_for_runner_event(
        resumed_runner,
        task_id,
        "task_interaction_required",
    )

    assert resume_result["ok"] is True
    assert resume_result["task_id"] == task_id
    assert resume_result["conversation_id"] == "conv_restart"
    assert resume_result["completed_step_ids"] == [1]
    assert replayed_event["data"]["request_id"] == request_id
    assert replayed_event["data"]["task_id"] == task_id

    response = resumed_runner.interaction_manager.respond(
        request_id,
        task_id=task_id,
        accepted=True,
    )
    final = resumed_runner.wait_for_task(task_id, timeout=5)
    restored = restart_store.load(task_id)

    assert response["ok"] is True
    assert final["status"] == "completed"
    assert tool.calls == 1
    assert restored is not None
    assert [step.status for step in restored.plan.steps] == ["completed", "completed"]
    assert len(restored.results) == 2
    assert restored.evidence["files"] == waiting_checkpoint.evidence["files"]
    assert restored.interaction_history[-1]["request_id"] == request_id
    assert restored.interaction_history[-1]["status"] == "accepted"


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


def test_runner_emits_versioned_events_with_conversation_ownership():
    runner = _make_runner(EventEnvelopeTask())

    task_id = runner.start("测试事件信封", conversation_id="conv_event")
    runner.wait_for_task(task_id, timeout=5)
    event = runner.get_result(task_id)["events"][0]

    assert event["version"] == 1
    assert event["event_id"].startswith("evt_")
    assert event["conversation_id"] == "conv_event"
    assert event["task_id"] == task_id
    assert event["type"] == "step_started"
    assert event["timestamp"]


def test_task_cancelled_error_is_exception():
    # 确保 TaskCancelledError 继承 Exception（被 except Exception 覆盖）
    assert issubclass(TaskCancelledError, Exception)
    assert not issubclass(TaskCancelledError, BaseException) or issubclass(
        TaskCancelledError, Exception
    )
