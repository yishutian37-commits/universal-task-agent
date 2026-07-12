from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from desktop.memory_compression import ALLOWED_MEMORY_KINDS, default_long_term_memory, merge_long_term_memory


class MemoryStore:
    def __init__(self, memory_root: Path | str):
        self.memory_root = Path(memory_root)

    def overview(self) -> dict[str, Any]:
        try:
            task_history = self._list_from_file("task_history.json", "tasks")
            lessons = self._list_from_file("lessons.json", "lessons")
            negative_rules = self._list_from_file("negative_rules.json", "negative_rules")
            skill_candidates = self._list_from_file("skill_candidates.json", "candidates")
            user_profile = self._dict_from_file("user_profile.json", "profile")
            long_term_memory = self.load_long_term_memory()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        long_term_facts = long_term_memory.get("facts") if isinstance(long_term_memory.get("facts"), list) else []
        return {
            "ok": True,
            "task_history": task_history,
            "lessons": lessons,
            "negative_rules": negative_rules,
            "skill_candidates": skill_candidates,
            "user_profile": user_profile,
            "long_term_memory": long_term_memory,
            "long_term_facts": long_term_facts,
            "counts": {
                "tasks": len(task_history),
                "lessons": len(lessons),
                "negative_rules": len(negative_rules),
                "skill_candidates": len(skill_candidates),
                "long_term_facts": len(long_term_facts),
            },
        }

    def load_long_term_memory(self) -> dict[str, Any]:
        path = self.memory_root / "long_term_memory.json"
        if not path.exists():
            return default_long_term_memory()
        payload = self._read_payload("long_term_memory.json")
        return merge_long_term_memory(payload, [], conversation_id="")

    def save_long_term_memory(self, memory: dict[str, Any]) -> None:
        self._write_payload("long_term_memory.json", memory)

    def merge_long_term_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        conversation_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        try:
            memory = self.load_long_term_memory()
            merged = merge_long_term_memory(memory, candidates, conversation_id=conversation_id, now=now)
            self.save_long_term_memory(merged)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "long_term_memory": merged}

    def search_long_term_facts(
        self,
        query: str = "",
        *,
        kind: str = "",
        include_disabled: bool = False,
    ) -> dict[str, Any]:
        try:
            memory = self.load_long_term_memory()
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "facts": []}
        needle = str(query or "").strip().casefold()
        kind_filter = str(kind or "").strip()
        facts = []
        for fact in memory.get("facts", []):
            if not isinstance(fact, dict):
                continue
            if fact.get("enabled") is False and not include_disabled:
                continue
            if kind_filter and str(fact.get("kind") or "") != kind_filter:
                continue
            searchable = " ".join(
                str(fact.get(field) or "")
                for field in ("content", "kind", "source_conversation_id", "memory_id")
            ).casefold()
            if needle and needle not in searchable:
                continue
            facts.append(dict(fact))
        return {"ok": True, "facts": facts, "count": len(facts)}

    def update_long_term_fact(
        self,
        memory_id: str,
        changes: dict[str, Any],
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        normalized_id = str(memory_id or "").strip()
        if not normalized_id:
            return {"ok": False, "error": "memory_id 不能为空"}
        if not isinstance(changes, dict):
            return {"ok": False, "error": "修改内容必须是对象"}
        try:
            memory = self.load_long_term_memory()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        fact = next(
            (
                item
                for item in memory.get("facts", [])
                if isinstance(item, dict) and str(item.get("memory_id") or "") == normalized_id
            ),
            None,
        )
        if fact is None:
            return {"ok": False, "error": "长期记忆不存在"}

        if "content" in changes:
            content = str(changes.get("content") or "").strip()
            if not content:
                return {"ok": False, "error": "长期记忆内容不能为空"}
            fact["content"] = content
        if "kind" in changes:
            kind = str(changes.get("kind") or "").strip()
            if kind not in ALLOWED_MEMORY_KINDS:
                return {"ok": False, "error": f"未知记忆类型: {kind}"}
            fact["kind"] = kind
        if "enabled" in changes:
            if not isinstance(changes.get("enabled"), bool):
                return {"ok": False, "error": "enabled 必须是布尔值"}
            fact["enabled"] = changes["enabled"]
        fact["updated_at"] = now or datetime.now(timezone.utc).isoformat()
        self._rebuild_long_term_profile(memory)
        self.save_long_term_memory(memory)
        return {"ok": True, "fact": dict(fact)}

    def delete_long_term_fact(self, memory_id: str) -> dict[str, Any]:
        normalized_id = str(memory_id or "").strip()
        try:
            memory = self.load_long_term_memory()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        facts = memory.get("facts", [])
        index = next(
            (
                index
                for index, item in enumerate(facts)
                if isinstance(item, dict) and str(item.get("memory_id") or "") == normalized_id
            ),
            None,
        )
        if index is None:
            return {"ok": False, "error": "长期记忆不存在"}
        fact = facts.pop(index)
        self._rebuild_long_term_profile(memory)
        self.save_long_term_memory(memory)
        return {"ok": True, "fact": fact}

    @staticmethod
    def _rebuild_long_term_profile(memory: dict[str, Any]) -> None:
        profile = default_long_term_memory()["profile"]
        buckets = {
            "identity": "identity",
            "preference": "preferences",
            "work_habit": "work_habits",
            "project": "projects",
            "constraint": "constraints",
            "decision": "decisions",
            "open_question": "open_questions",
        }
        for fact in memory.get("facts", []):
            if not isinstance(fact, dict) or fact.get("enabled") is False:
                continue
            bucket = buckets.get(str(fact.get("kind") or ""))
            content = str(fact.get("content") or "").strip()
            if bucket and content and content not in profile[bucket]:
                profile[bucket].append(content)
        memory["profile"] = profile

    def _list_from_file(self, filename: str, key: str) -> list[dict[str, Any]]:
        payload = self._read_payload(filename)
        value = payload.get(key, [])
        return value if isinstance(value, list) else []

    def _dict_from_file(self, filename: str, key: str) -> dict[str, Any]:
        payload = self._read_payload(filename)
        value = payload.get(key, {})
        return value if isinstance(value, dict) else {}

    def _read_payload(self, filename: str) -> dict[str, Any]:
        path = self.memory_root / filename
        if not path.exists():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{filename} 无法读取或 JSON 无效") from exc
        return parsed if isinstance(parsed, dict) else {}

    def _write_payload(self, filename: str, payload: dict[str, Any]) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        path = self.memory_root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
