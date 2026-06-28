import pytest

from core.state import Feedback
from tools.text_tool import TextTool


class FakeLLMClient:
    def __init__(self, response="## 摘要\n库存接口已完成联调。"):
        self.response = response
        self.calls = []

    def chat(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


def test_text_tool_summarizes_previous_content_with_llm():
    client = FakeLLMClient()
    result = TextTool(llm_client=client).run(
        "process",
        {
            "user_input": "帮我总结",
            "previous_result": {"content": "会议记录：库存接口已完成联调。"},
        },
    )

    assert result["summary_markdown"] == "## 摘要\n库存接口已完成联调。"
    assert result["message"] == "## 摘要\n库存接口已完成联调。"
    assert "会议记录：库存接口已完成联调。" in client.calls[0][1]


def test_text_tool_rejects_empty_text():
    with pytest.raises(ValueError, match="没有可总结的文本"):
        TextTool(llm_client=FakeLLMClient()).run(
            "process",
            {"user_input": "", "previous_result": {"content": ""}},
        )


def test_text_tool_includes_feedback_in_retry_prompt():
    client = FakeLLMClient()
    feedback = Feedback(
        failure_type="incomplete_output",
        root_cause="缺少必要小节：风险点",
        repair_strategy="补齐风险点小节",
    )

    TextTool(llm_client=client).run(
        "process",
        {
            "user_input": "帮我总结",
            "previous_result": {"content": "会议记录：库存接口已完成联调。"},
            "feedback": feedback,
        },
    )

    assert "上一次输出未通过校验" in client.calls[0][1]
    assert "补齐风险点小节" in client.calls[0][1]


def test_text_tool_includes_complex_step_goal_in_prompt():
    client = FakeLLMClient()

    TextTool(llm_client=client).run(
        "process",
        {
            "user_input": "原文：这是一篇讨论工具理性的文章。",
            "goal": "改写成适合小白看的版本",
        },
    )

    assert "当前步骤目标：改写成适合小白看的版本" in client.calls[0][1]
    assert "请围绕当前步骤目标处理下面文本" in client.calls[0][1]
