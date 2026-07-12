from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def desktop_event(
    event: dict[str, Any],
    *,
    conversation_id: str = "",
    task_id: str = "",
    now: datetime | None = None,
    event_id: str = "",
) -> dict[str, Any]:
    source = dict(event or {})
    timestamp = source.get("timestamp") or (now or datetime.now(timezone.utc)).isoformat()
    data = source.get("data")
    if not isinstance(data, dict):
        data = {"value": data} if data is not None else {}
    return {
        "version": int(source.get("version") or 1),
        "event_id": str(source.get("event_id") or event_id or f"evt_{uuid4().hex}"),
        "conversation_id": str(source.get("conversation_id") or conversation_id or ""),
        "task_id": str(source.get("task_id") or task_id or ""),
        "type": str(source.get("type") or "unknown"),
        "timestamp": str(timestamp),
        "data": data,
    }

