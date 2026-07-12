import threading
import time

import pytest


def test_authorization_manager_emits_request_and_returns_approval():
    from tools.authorization import AuthorizationManager

    emitted = []
    manager = AuthorizationManager(on_request=emitted.append)
    result_holder = {}

    def worker():
        result_holder["decision"] = manager.request(
            {"tool_name": "langchain_shell_tool", "summary": "执行 echo"},
            timeout=1,
        )

    thread = threading.Thread(target=worker)
    thread.start()

    deadline = time.time() + 1
    while not emitted and time.time() < deadline:
        time.sleep(0.01)

    assert emitted
    request_id = emitted[0]["request_id"]
    assert emitted[0]["status"] == "pending"

    approved = manager.approve(request_id, approved_by="tester")
    thread.join(timeout=1)

    assert approved == {"ok": True, "request_id": request_id, "status": "approved"}
    assert result_holder["decision"].approved is True
    assert result_holder["decision"].request_id == request_id
    assert result_holder["decision"].approved_by == "tester"


def test_authorization_manager_returns_rejection():
    from tools.authorization import AuthorizationManager

    emitted = []
    manager = AuthorizationManager(on_request=emitted.append)
    result_holder = {}

    thread = threading.Thread(
        target=lambda: result_holder.update(
            decision=manager.request({"tool_name": "langchain_file_write_tool"}, timeout=1)
        )
    )
    thread.start()

    deadline = time.time() + 1
    while not emitted and time.time() < deadline:
        time.sleep(0.01)

    request_id = emitted[0]["request_id"]
    rejected = manager.reject(request_id, reason="用户拒绝")
    thread.join(timeout=1)

    assert rejected == {"ok": True, "request_id": request_id, "status": "rejected"}
    assert result_holder["decision"].approved is False
    assert result_holder["decision"].reason == "用户拒绝"


def test_authorization_manager_times_out_pending_request():
    from tools.authorization import AuthorizationManager

    manager = AuthorizationManager()

    decision = manager.request({"tool_name": "langchain_shell_tool"}, timeout=0.01)

    assert decision.approved is False
    assert decision.status == "timeout"
    assert "超时" in decision.reason


def test_authorization_manager_reports_unknown_request_id():
    from tools.authorization import AuthorizationManager

    manager = AuthorizationManager()

    assert manager.approve("missing") == {"ok": False, "error": "授权请求不存在"}
    assert manager.reject("missing") == {"ok": False, "error": "授权请求不存在"}
