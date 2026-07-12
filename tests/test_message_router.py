from __future__ import annotations

from desktop.message_router import MessageRouter


class FakeStructuredClient:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls = []

    def chat_json(self, system_prompt, user_prompt, schema=None):
        self.calls.append((system_prompt, user_prompt, schema))
        if self.error is not None:
            raise self.error
        return self.payload


def test_message_router_uses_model_for_ambiguous_task():
    client = FakeStructuredClient(
        {"kind": "task", "reason": "需要读取并整理材料", "confidence": 0.91, "reply": ""}
    )

    decision = MessageRouter().route("把这些材料处理一下", context="同一对话前文", client=client)

    assert decision.kind == "task"
    assert decision.source == "model"
    assert decision.reason == "需要读取并整理材料"
    assert decision.confidence == 0.91
    assert "同一对话前文" in client.calls[0][1]


def test_message_router_keeps_model_chat_reply_for_single_call_response():
    client = FakeStructuredClient(
        {"kind": "chat", "reason": "这是创意讨论", "confidence": 0.88, "reply": "可以叫星河计划。"}
    )

    decision = MessageRouter().route("帮我想一个项目名字", context="", client=client)

    assert decision.kind == "chat"
    assert decision.reply == "可以叫星河计划。"
    assert len(client.calls) == 1


def test_message_router_cannot_downgrade_dangerous_operation_to_chat():
    client = FakeStructuredClient(
        {"kind": "chat", "reason": "可以直接回答", "confidence": 0.99, "reply": "已经删除。"}
    )

    decision = MessageRouter().route("删除文件 notes.txt", context="", client=client)

    assert decision.kind == "task"
    assert decision.source == "safety"
    assert decision.reply == ""


def test_message_router_falls_back_when_model_output_is_invalid():
    client = FakeStructuredClient({"kind": "unknown", "reason": "", "confidence": "high"})

    decision = MessageRouter().route("帮我总结这段文本", context="", client=client)

    assert decision.kind == "task"
    assert decision.source == "fallback"


def test_message_router_falls_back_for_clients_without_structured_output():
    class ChatOnlyClient:
        pass

    decision = MessageRouter().route("你好", context="", client=ChatOnlyClient())

    assert decision.kind == "chat"
    assert decision.source == "fallback"

