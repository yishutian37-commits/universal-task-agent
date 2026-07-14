from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading
import uuid
from typing import Any, Callable


@dataclass
class InteractionDecision:
    request_id: str
    accepted: bool
    status: str
    response: str = ""
    steps: list[Any] = field(default_factory=list)


class _PendingInteraction:
    def __init__(self, request: dict[str, Any]) -> None:
        self.request = request
        self.event = threading.Event()
        self.decision: InteractionDecision | None = None


class TaskInteractionManager:
    def __init__(self, on_request: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.on_request = on_request
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingInteraction] = {}
        self._decisions: dict[str, tuple[str, InteractionDecision]] = {}

    def request(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        task_id: str,
        request_id: str | None = None,
        created_at: str | None = None,
        timeout: float | None = None,
    ) -> InteractionDecision:
        request_id = str(request_id or "interaction_" + uuid.uuid4().hex)
        task_id = str(task_id or "")
        request = dict(payload)
        request.update(
            {
                "request_id": request_id,
                "task_id": task_id,
                "kind": str(kind or "user_input"),
                "status": "pending",
                "created_at": str(
                    created_at or datetime.now().isoformat(timespec="seconds")
                ),
            }
        )
        with self._lock:
            completed = self._decisions.get(request_id)
            if completed is not None:
                owner_task_id, decision = completed
                if owner_task_id != task_id:
                    return InteractionDecision(
                        request_id=request_id,
                        accepted=False,
                        status="rejected",
                        response="交互请求不属于当前任务",
                    )
                return decision
            pending = self._pending.get(request_id)
            should_emit = pending is None
            if pending is None:
                pending = _PendingInteraction(request)
                self._pending[request_id] = pending
            elif str(pending.request.get("task_id") or "") != task_id:
                return InteractionDecision(
                    request_id=request_id,
                    accepted=False,
                    status="rejected",
                    response="交互请求不属于当前任务",
                )

        if should_emit and self.on_request is not None:
            self.on_request(dict(request))

        if not pending.event.wait(timeout=timeout):
            with self._lock:
                current = self._pending.get(request_id)
                if current is pending and pending.decision is None:
                    self._pending.pop(request_id, None)
                    pending.decision = InteractionDecision(
                        request_id=request_id,
                        accepted=False,
                        status="timeout",
                        response="等待用户回复超时",
                    )
                    self._decisions[request_id] = (task_id, pending.decision)
                decision = pending.decision
            return decision or InteractionDecision(
                request_id=request_id,
                accepted=False,
                status="timeout",
                response="等待用户回复超时",
            )
        return pending.decision or InteractionDecision(
            request_id=request_id,
            accepted=False,
            status="rejected",
            response="用户未确认",
        )

    def respond(
        self,
        request_id: str,
        *,
        task_id: str | None = None,
        accepted: bool,
        response: str = "",
        steps: list[Any] | None = None,
    ) -> dict[str, Any]:
        request_id = str(request_id or "")
        task_id = str(task_id or "")
        with self._lock:
            completed = self._decisions.get(request_id)
            if completed is not None:
                owner_task_id, decision = completed
                if task_id and owner_task_id != task_id:
                    return {"ok": False, "error": "交互请求不属于当前任务"}
                return {
                    "ok": True,
                    "request_id": request_id,
                    "status": decision.status,
                    "duplicate": True,
                }

            pending = self._pending.get(request_id)
            if pending is None:
                return {"ok": False, "error": "交互请求不存在或已过期"}
            owner_task_id = str(pending.request.get("task_id") or "")
            if task_id and owner_task_id != task_id:
                return {"ok": False, "error": "交互请求不属于当前任务"}

            self._pending.pop(request_id, None)
            status = "accepted" if accepted else "rejected"
            pending.decision = InteractionDecision(
                request_id=request_id,
                accepted=bool(accepted),
                status=status,
                response=str(response or ""),
                steps=list(steps or []),
            )
            self._decisions[request_id] = (owner_task_id, pending.decision)
        pending.event.set()
        return {
            "ok": True,
            "request_id": request_id,
            "status": status,
            "duplicate": False,
        }

    def cancel_for_task(self, task_id: str) -> int:
        task_id = str(task_id or "")
        cancelled: list[_PendingInteraction] = []
        with self._lock:
            for request_id, pending in list(self._pending.items()):
                if str(pending.request.get("task_id") or "") != task_id:
                    continue
                self._pending.pop(request_id, None)
                pending.decision = InteractionDecision(
                    request_id=request_id,
                    accepted=False,
                    status="cancelled",
                    response="任务已取消",
                )
                self._decisions[request_id] = (task_id, pending.decision)
                cancelled.append(pending)
        for pending in cancelled:
            pending.event.set()
        return len(cancelled)
