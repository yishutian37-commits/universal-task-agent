from __future__ import annotations

import json
from dataclasses import dataclass
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
