from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any


ALLOWED_MEMORY_KINDS = frozenset(
    {
        "identity",
        "preference",
        "work_habit",
        "project",
        "constraint",
        "decision",
        "open_question",
    }
)


class CompressionFormatError(ValueError):
    pass


def estimate_tokens(text: str) -> int:
    return max(1, (len(str(text or "")) + 3) // 4)


@dataclass(frozen=True)
class CompressionPolicy:
    context_window_tokens: int = 400_000
    trigger_ratio: float = 0.70
    trigger_cap_tokens: int = 250_000
    target_recent_messages: int = 12

    @property
    def trigger_tokens(self) -> int:
        return int(min(self.trigger_cap_tokens, self.context_window_tokens * self.trigger_ratio))

    def should_compress(self, token_estimate: int) -> bool:
        return int(token_estimate) >= self.trigger_tokens


def parse_compression_result(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CompressionFormatError("压缩结果必须是 JSON") from exc
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        raise CompressionFormatError("压缩结果必须是 JSON")

    if not isinstance(data, dict):
        raise CompressionFormatError("压缩结果必须是 JSON 对象")

    summary = data.get("short_term_summary")
    if not isinstance(summary, str):
        raise CompressionFormatError("short_term_summary 必须是字符串")

    candidates = data.get("long_term_candidates", [])
    if not isinstance(candidates, list):
        raise CompressionFormatError("long_term_candidates 必须是数组")

    normalized_candidates = [_normalize_candidate(candidate) for candidate in candidates]

    open_questions = data.get("open_questions", [])
    if not isinstance(open_questions, list):
        raise CompressionFormatError("open_questions 必须是数组")

    return {
        "short_term_summary": summary.strip(),
        "long_term_candidates": normalized_candidates,
        "open_questions": [str(question).strip() for question in open_questions if str(question).strip()],
    }


def default_long_term_memory() -> dict[str, Any]:
    return {
        "version": 1,
        "profile": {
            "identity": [],
            "preferences": [],
            "work_habits": [],
            "projects": [],
            "constraints": [],
            "open_questions": [],
            "decisions": [],
        },
        "facts": [],
    }


def merge_long_term_memory(
    memory: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    *,
    conversation_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    merged = _normalize_long_term_memory(memory)
    timestamp = now or datetime.now().isoformat(timespec="microseconds")
    facts = merged["facts"]
    by_key = {
        (str(fact.get("kind") or ""), str(fact.get("content") or "")): fact
        for fact in facts
        if isinstance(fact, dict)
    }

    for candidate in candidates:
        normalized = _normalize_candidate(candidate)
        key = (normalized["kind"], normalized["content"])
        existing = by_key.get(key)
        if existing is None:
            fact = {
                "memory_id": _memory_id(),
                "kind": normalized["kind"],
                "content": normalized["content"],
                "source_conversation_id": conversation_id,
                "source_message_ids": normalized["source_message_ids"],
                "confidence": normalized["confidence"],
                "first_seen_at": timestamp,
                "last_seen_at": timestamp,
            }
            facts.append(fact)
            by_key[key] = fact
        else:
            existing["last_seen_at"] = timestamp
            existing["confidence"] = max(float(existing.get("confidence") or 0), normalized["confidence"])
            existing["source_message_ids"] = _merge_unique(
                existing.get("source_message_ids", []),
                normalized["source_message_ids"],
            )
            existing.setdefault("source_conversation_id", conversation_id)
        _append_profile_value(merged["profile"], normalized["kind"], normalized["content"])

    return merged


def _normalize_candidate(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise CompressionFormatError("长期记忆候选必须是对象")

    kind = str(candidate.get("kind") or "").strip()
    if kind not in ALLOWED_MEMORY_KINDS:
        raise CompressionFormatError(f"未知记忆类型: {kind}")

    content = str(candidate.get("content") or "").strip()
    if not content:
        raise CompressionFormatError("长期记忆内容不能为空")

    try:
        confidence = float(candidate.get("confidence", 0.7))
    except (TypeError, ValueError) as exc:
        raise CompressionFormatError("confidence 必须是数字") from exc
    if confidence < 0 or confidence > 1:
        raise CompressionFormatError("confidence 必须在 0 到 1 之间")

    source_message_ids = candidate.get("source_message_ids", [])
    if not isinstance(source_message_ids, list):
        raise CompressionFormatError("source_message_ids 必须是数组")

    return {
        "kind": kind,
        "content": content,
        "confidence": confidence,
        "source_message_ids": [
            str(message_id).strip() for message_id in source_message_ids if str(message_id).strip()
        ],
    }


def _normalize_long_term_memory(memory: dict[str, Any] | None) -> dict[str, Any]:
    normalized = default_long_term_memory()
    if not isinstance(memory, dict):
        return normalized

    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
    for key, default_value in normalized["profile"].items():
        value = profile.get(key, default_value)
        normalized["profile"][key] = list(value) if isinstance(value, list) else []

    facts = memory.get("facts")
    normalized["facts"] = deepcopy(facts) if isinstance(facts, list) else []
    return normalized


def _append_profile_value(profile: dict[str, list[str]], kind: str, content: str) -> None:
    bucket = _profile_key_for_kind(kind)
    if bucket is None:
        return
    values = profile.setdefault(bucket, [])
    if content not in values:
        values.append(content)


def _profile_key_for_kind(kind: str) -> str | None:
    return {
        "identity": "identity",
        "preference": "preferences",
        "work_habit": "work_habits",
        "project": "projects",
        "constraint": "constraints",
        "decision": "decisions",
        "open_question": "open_questions",
    }.get(kind)


def _merge_unique(left: Any, right: Any) -> list[str]:
    merged: list[str] = []
    for value in list(left if isinstance(left, list) else []) + list(right if isinstance(right, list) else []):
        item = str(value).strip()
        if item and item not in merged:
            merged.append(item)
    return merged


def _memory_id() -> str:
    return "mem_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
