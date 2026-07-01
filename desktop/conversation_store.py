from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class ConversationStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def new_conversation(self, title: str | None = None) -> dict[str, Any]:
        now = _now()
        conversation = {
            "conversation_id": _conversation_id(),
            "title": title or "新对话",
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "short_term": _default_short_term(),
            "compression": _default_compression(),
        }
        self._write(conversation)
        return {"ok": True, "conversation": conversation}

    def list_conversations(self) -> dict[str, Any]:
        if not self.root.exists():
            return {"ok": True, "conversations": []}

        items = []
        for path in self.root.glob("conv_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue

            conversation_id = str(data.get("conversation_id") or "")
            if not _is_safe_id(conversation_id):
                continue

            messages = data.get("messages") if isinstance(data.get("messages"), list) else []
            preview = str(messages[-1].get("content") or "")[:120] if messages else ""
            items.append(
                {
                    "conversation_id": conversation_id,
                    "title": str(data.get("title") or "新对话"),
                    "updated_at": str(data.get("updated_at") or ""),
                    "message_count": len(messages),
                    "preview": preview,
                }
            )
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"ok": True, "conversations": items}

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        path = self._path_for(conversation_id)
        if path is None or not path.exists() or path.is_symlink():
            return {"ok": False, "error": "会话不存在"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "error": "会话 JSON 无效"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "会话 JSON 无效"}
        data.setdefault("short_term", _default_short_term())
        data.setdefault("compression", _default_compression())
        return {"ok": True, "conversation": data}

    def append_message(
        self,
        conversation_id: str,
        *,
        role: str,
        content: str,
        task_id: str | None = None,
        status: str = "completed",
    ) -> dict[str, Any]:
        loaded = self.get_conversation(conversation_id)
        if not loaded.get("ok"):
            return loaded

        conversation = loaded["conversation"]
        message = {
            "message_id": _message_id(),
            "role": role,
            "content": content,
            "task_id": task_id,
            "status": status,
            "created_at": _now(),
        }
        conversation.setdefault("messages", []).append(message)
        conversation["updated_at"] = message["created_at"]
        if role == "user" and len(conversation["messages"]) == 1:
            conversation["title"] = content[:30] or conversation.get("title") or "新对话"
        self._write(conversation)
        return {"ok": True, "message": message, "conversation": conversation}

    def update_assistant_message(
        self,
        conversation_id: str,
        *,
        task_id: str,
        content: str,
        status: str,
    ) -> dict[str, Any]:
        loaded = self.get_conversation(conversation_id)
        if not loaded.get("ok"):
            return loaded

        conversation = loaded["conversation"]
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        for message in reversed(messages):
            if message.get("role") == "assistant" and message.get("task_id") == task_id:
                message["content"] = content
                message["status"] = status
                message["updated_at"] = _now()
                conversation["updated_at"] = message["updated_at"]
                self._write(conversation)
                return {"ok": True, "message": message, "conversation": conversation}
        return {"ok": False, "error": "助手消息不存在"}

    def _path_for(self, conversation_id: str) -> Path | None:
        if not _is_safe_id(str(conversation_id or "")):
            return None
        return self.root / f"{conversation_id}.json"

    def _write(self, conversation: dict[str, Any]) -> None:
        path = self._path_for(str(conversation.get("conversation_id") or ""))
        if path is None:
            raise ValueError("会话 ID 无效")
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _conversation_id() -> str:
    return "conv_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _message_id() -> str:
    return "msg_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _default_short_term() -> dict[str, Any]:
    return {
        "summary": "",
        "compressed_until_index": 0,
        "recent_message_limit": 12,
        "token_estimate": 0,
        "updated_at": "",
    }


def _default_compression() -> dict[str, Any]:
    return {
        "last_compressed_at": "",
        "last_trigger_tokens": 0,
        "runs": [],
    }


def _is_safe_id(value: str) -> bool:
    return bool(re.fullmatch(r"conv_[0-9]{8}_[0-9]{6}_[0-9]{6}", value))
