"""TaskRunner 取消机制测试。

验证基于 on_progress 检查点的软取消：
- cancel 设置取消标志 → 下一个 _emit_progress 检查点抛 TaskCancelledError
- _run 捕获后把结果记成 status=cancelled
"""
from __future__ import annotations

import threading
import time

import pytest

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
