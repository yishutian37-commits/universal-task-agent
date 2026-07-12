from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
import uuid
from typing import Any, Callable


@dataclass
class AuthorizationDecision:
    request_id: str
    approved: bool
    status: str
    approved_by: str = ""
    reason: str = ""


class _PendingAuthorization:
    def __init__(self, request: dict[str, Any]) -> None:
        self.request = request
        self.event = threading.Event()
        self.decision: AuthorizationDecision | None = None


class AuthorizationManager:
    def __init__(self, on_request: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.on_request = on_request
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingAuthorization] = {}

    def request(
        self,
        operation: dict[str, Any],
        timeout: float | None = None,
    ) -> AuthorizationDecision:
        request_id = "auth_" + uuid.uuid4().hex
        request = dict(operation)
        request.update(
            {
                "request_id": request_id,
                "status": "pending",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        pending = _PendingAuthorization(request)
        with self._lock:
            self._pending[request_id] = pending

        if self.on_request is not None:
            self.on_request(dict(request))

        if not pending.event.wait(timeout=timeout):
            decision = AuthorizationDecision(
                request_id=request_id,
                approved=False,
                status="timeout",
                reason="授权等待超时",
            )
            with self._lock:
                self._pending.pop(request_id, None)
            return decision

        return pending.decision or AuthorizationDecision(
            request_id=request_id,
            approved=False,
            status="rejected",
            reason="授权请求未通过",
        )

    def approve(self, request_id: str, approved_by: str = "user") -> dict[str, Any]:
        pending = self._pop_pending(request_id)
        if pending is None:
            return {"ok": False, "error": "授权请求不存在"}
        pending.decision = AuthorizationDecision(
            request_id=request_id,
            approved=True,
            status="approved",
            approved_by=approved_by,
        )
        pending.event.set()
        return {"ok": True, "request_id": request_id, "status": "approved"}

    def reject(self, request_id: str, reason: str = "") -> dict[str, Any]:
        pending = self._pop_pending(request_id)
        if pending is None:
            return {"ok": False, "error": "授权请求不存在"}
        pending.decision = AuthorizationDecision(
            request_id=request_id,
            approved=False,
            status="rejected",
            reason=reason or "用户拒绝授权",
        )
        pending.event.set()
        return {"ok": True, "request_id": request_id, "status": "rejected"}

    def _pop_pending(self, request_id: str) -> _PendingAuthorization | None:
        with self._lock:
            return self._pending.pop(str(request_id or ""), None)
