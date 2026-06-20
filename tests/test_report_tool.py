from tools.report_tool import ReportTool


def test_report_tool_uses_summary_markdown_as_final_message():
    result = ReportTool().run(
        "generate",
        {"previous_result": {"summary_markdown": "## 摘要\n库存接口已完成联调。"}},
    )

    assert result["message"] == "## 摘要\n库存接口已完成联调。"
    assert result["report_markdown"] == "## 摘要\n库存接口已完成联调。"


def test_report_tool_returns_clear_message_without_summary():
    result = ReportTool().run("generate", {"previous_result": {}})

    assert result["message"] == "未生成总结报告"
    assert result["report_markdown"] == "未生成总结报告"
