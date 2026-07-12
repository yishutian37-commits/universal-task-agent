from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.intent_rules import (
    looks_like_dangerous_tool_request,
    looks_like_named_file_read,
    looks_like_workspace_file_request,
)
from desktop.chat_router import chat_route_kind


ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["chat", "task"]},
        "reason": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reply": {"type": "string"},
    },
    "required": ["kind", "reason", "confidence", "reply"],
}

ROUTER_SYSTEM_PROMPT = (
    "你是 UTA Desktop 的消息路由与对话模型。先理解用户当前消息以及同一对话前文，再判断："
    "chat 表示只需要解释、讨论、建议、创意或普通问答；task 表示需要拆解步骤、读取资料、调用工具、"
    "修改文件、搜索、计算或生成可验证产物。不要因为出现‘帮我’等单个词就判定为 task。"
    "如果判断为 chat，请直接在 reply 中给出简洁、诚实、中文的最终回复；如果判断为 task，reply 必须为空字符串。"
    "UTA 不能控制鼠标、键盘或其他本地应用，但可以在授权后通过受控工具处理工作区文件、Shell 和 Python。"
    "只返回符合给定结构的 JSON 对象，不要输出 Markdown。"
)


@dataclass(frozen=True)
class RouteDecision:
    kind: str
    reason: str
    confidence: float
    reply: str = ""
    source: str = "model"


class MessageRouter:
    def route(self, text: str, *, context: str = "", client: Any = None) -> RouteDecision:
        fallback = self._fallback(text)
        decision = self._model_decision(text, context=context, client=client)
        if decision is None:
            decision = fallback

        if self._must_run_as_task(text):
            return RouteDecision(
                kind="task",
                reason="请求涉及本地文件或高风险工具，必须进入受控任务流程",
                confidence=1.0,
                source="safety",
            )
        return decision

    def _model_decision(self, text: str, *, context: str, client: Any) -> RouteDecision | None:
        chat_json = getattr(client, "chat_json", None)
        if not callable(chat_json):
            return None

        context_text = context.strip() or "（无同一对话前文）"
        user_prompt = f"同一对话前文：\n{context_text}\n\n当前消息：\n{text.strip()}"
        try:
            payload = chat_json(ROUTER_SYSTEM_PROMPT, user_prompt, schema=ROUTE_SCHEMA)
            return self._validate_payload(payload)
        except Exception:
            return None

    @staticmethod
    def _validate_payload(payload: Any) -> RouteDecision | None:
        if not isinstance(payload, dict):
            return None
        kind = str(payload.get("kind") or "").strip().lower()
        reason = str(payload.get("reason") or "").strip()
        reply = str(payload.get("reply") or "").strip()
        confidence = payload.get("confidence")
        if kind not in {"chat", "task"} or not reason:
            return None
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return None
        confidence = float(confidence)
        if not 0 <= confidence <= 1:
            return None
        if kind == "task":
            reply = ""
        return RouteDecision(kind=kind, reason=reason, confidence=confidence, reply=reply, source="model")

    @staticmethod
    def _fallback(text: str) -> RouteDecision:
        route_kind = chat_route_kind(text)
        kind = "task" if route_kind == "task" else "chat"
        return RouteDecision(
            kind=kind,
            reason="模型路由不可用，已使用本地兼容规则",
            confidence=0.5,
            source="fallback",
        )

    @staticmethod
    def _must_run_as_task(text: str) -> bool:
        return (
            looks_like_dangerous_tool_request(text)
            or looks_like_workspace_file_request(text)
            or looks_like_named_file_read(text)
        )

