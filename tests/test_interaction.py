import threading
import time

from core.interaction import TaskInteractionManager


def _wait_for_request(requests):
    deadline = time.time() + 2
    while not requests and time.time() < deadline:
        time.sleep(0.01)
    assert requests


def test_interaction_manager_waits_for_and_returns_user_response():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "missing_info",
                {"question": "请提供文件路径"},
                task_id="task_1",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    result = manager.respond(
        requests[0]["request_id"],
        accepted=True,
        response="/tmp/input.md",
    )
    thread.join(timeout=2)

    assert result["ok"] is True
    assert decisions[0].accepted is True
    assert decisions[0].response == "/tmp/input.md"
    assert decisions[0].status == "accepted"


def test_interaction_manager_restores_stable_request_identity():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "missing_info",
                {"question": "请提供文件路径"},
                task_id="task_restore",
                request_id="interaction_stable",
                created_at="2026-07-14T10:00:00",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    result = manager.respond(
        "interaction_stable",
        task_id="task_restore",
        accepted=True,
        response="/tmp/input.md",
    )
    thread.join(timeout=2)

    assert requests[0]["request_id"] == "interaction_stable"
    assert requests[0]["created_at"] == "2026-07-14T10:00:00"
    assert result == {
        "ok": True,
        "request_id": "interaction_stable",
        "status": "accepted",
        "duplicate": False,
    }
    assert decisions[0].request_id == "interaction_stable"


def test_interaction_manager_duplicate_response_retains_first_decision():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "missing_info",
                {"question": "请补充信息"},
                task_id="task_duplicate",
                request_id="interaction_duplicate",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    first = manager.respond(
        "interaction_duplicate",
        task_id="task_duplicate",
        accepted=True,
        response="第一次回复",
    )
    second = manager.respond(
        "interaction_duplicate",
        task_id="task_duplicate",
        accepted=False,
        response="第二次回复",
    )
    thread.join(timeout=2)

    assert first["duplicate"] is False
    assert second == {
        "ok": True,
        "request_id": "interaction_duplicate",
        "status": "accepted",
        "duplicate": True,
    }
    assert decisions[0].accepted is True
    assert decisions[0].response == "第一次回复"


def test_interaction_manager_rejects_foreign_task_without_consuming_request():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "missing_info",
                {"question": "请补充信息"},
                task_id="task_owner",
                request_id="interaction_owned",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    foreign = manager.respond(
        "interaction_owned",
        task_id="task_other",
        accepted=True,
    )
    owner = manager.respond(
        "interaction_owned",
        task_id="task_owner",
        accepted=False,
    )
    thread.join(timeout=2)

    assert foreign == {"ok": False, "error": "交互请求不属于当前任务"}
    assert owner["ok"] is True
    assert decisions[0].status == "rejected"


def test_interaction_manager_rejects_stale_request():
    manager = TaskInteractionManager()

    assert manager.respond(
        "interaction_missing",
        task_id="task_missing",
        accepted=True,
    ) == {"ok": False, "error": "交互请求不存在或已过期"}


def test_interaction_manager_can_return_edited_plan_steps():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "plan_confirmation",
                {"steps": [{"step_id": 1, "goal": "原步骤"}]},
                task_id="task_2",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    manager.respond(
        requests[0]["request_id"],
        accepted=True,
        steps=["新步骤一", "新步骤二"],
    )
    thread.join(timeout=2)

    assert decisions[0].steps == ["新步骤一", "新步骤二"]


def test_interaction_manager_cancel_for_task_wakes_pending_request():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)
    decisions = []
    thread = threading.Thread(
        target=lambda: decisions.append(
            manager.request(
                "missing_info",
                {"question": "请补充信息"},
                task_id="task_cancel",
                timeout=2,
            )
        )
    )

    thread.start()
    _wait_for_request(requests)
    cancelled = manager.cancel_for_task("task_cancel")
    thread.join(timeout=2)

    assert cancelled == 1
    assert decisions[0].accepted is False
    assert decisions[0].status == "cancelled"
    assert manager.respond(
        requests[0]["request_id"],
        task_id="task_cancel",
        accepted=True,
    ) == {
        "ok": True,
        "request_id": requests[0]["request_id"],
        "status": "cancelled",
        "duplicate": True,
    }


def test_interaction_manager_timeout_is_terminal_and_idempotent():
    requests = []
    manager = TaskInteractionManager(on_request=requests.append)

    decision = manager.request(
        "missing_info",
        {"question": "请补充信息"},
        task_id="task_timeout",
        request_id="interaction_timeout",
        timeout=0.01,
    )
    duplicate = manager.respond(
        "interaction_timeout",
        task_id="task_timeout",
        accepted=True,
    )

    assert decision.status == "timeout"
    assert decision.accepted is False
    assert duplicate == {
        "ok": True,
        "request_id": "interaction_timeout",
        "status": "timeout",
        "duplicate": True,
    }
