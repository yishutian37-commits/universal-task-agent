import pytest

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
