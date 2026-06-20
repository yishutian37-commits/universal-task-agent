from core.state import AgentState, PlanStep, ToolResult
from core.verifier import Verifier


def test_verifier_passes_successful_tool_result():
    result = ToolResult(
        success=True,
        tool_name="mock_tool",
        action_name="run",
        result={"message": "mock result"},
    )

    check = Verifier().check(result)

    assert check.passed is True
    assert check.failed_reasons == []
    assert check.suggested_fix == []


def test_verifier_fails_unsuccessful_tool_result():
    result = ToolResult(
        success=False,
        tool_name="mock_tool",
        action_name="run",
        result={},
        error="tool_unavailable: mock_tool",
    )

    check = Verifier().check(result)

    assert check.passed is False
    assert check.failed_reasons == ["工具执行失败：tool_unavailable: mock_tool"]
    assert check.suggested_fix == ["检查工具名称或工具实现"]


def test_verifier_passes_complete_summary_report():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": "## 摘要\n完成联调。\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is True
    assert check.failed_reasons == []


def test_verifier_fails_summary_missing_risk_section():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={"message": "## 摘要\n完成联调。\n## 核心观点\n流程清晰。"},
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "缺少必要小节：风险点" in check.failed_reasons
    assert "补齐风险点小节" in check.suggested_fix


def test_verifier_fails_summary_empty_section():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={"message": "## 摘要\n\n## 核心观点\n流程清晰。\n## 风险点\n原文未提供明确风险。"},
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "小节内容为空：摘要" in check.failed_reasons
    assert "补充摘要小节内容" in check.suggested_fix
