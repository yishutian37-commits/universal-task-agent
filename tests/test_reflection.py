from core.reflection import Reflection
from core.state import AgentState, CheckResult, PlanStep, ToolResult


def test_reflection_classifies_incomplete_output():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=3, goal="生成结构化报告")
    result = ToolResult(True, "report_tool", "generate", {"message": "## 摘要\n完成联调。"})
    check = CheckResult(
        passed=False,
        failed_reasons=["缺少必要小节：风险点"],
        suggested_fix=["补齐风险点小节"],
    )

    feedback = Reflection().analyze(state, step, result, check)

    assert feedback.failure_type == "incomplete_output"
    assert feedback.root_cause == "缺少必要小节：风险点"
    assert feedback.repair_strategy == "补齐风险点小节"
    assert feedback.need_replan is False
    assert feedback.need_user_input is False


def test_reflection_classifies_tool_error():
    state = AgentState(task_id="task_test", user_input="帮我总结", task_type="summarize")
    step = PlanStep(step_id=2, goal="提取核心信息")
    result = ToolResult(False, "text_tool", "process", {}, error="tool_error: boom")
    check = CheckResult(
        passed=False,
        failed_reasons=["工具执行失败：tool_error: boom"],
        suggested_fix=["检查工具名称或工具实现"],
    )

    feedback = Reflection().analyze(state, step, result, check)

    assert feedback.failure_type == "tool_error"
    assert "tool_error: boom" in feedback.root_cause


def test_reflection_requests_user_input_when_required_file_path_is_missing():
    state = AgentState(task_id="task_test", user_input="读取那个文件", task_type="code_reading")
    step = PlanStep(step_id=1, goal="读取目标文件")
    result = ToolResult(
        False,
        "file_tool",
        "read",
        {},
        error="tool_error: 文件路径不存在",
    )
    check = CheckResult(
        passed=False,
        failed_reasons=["工具执行失败：tool_error: 文件路径不存在"],
        suggested_fix=["请提供正确文件路径"],
    )

    feedback = Reflection().analyze(state, step, result, check)

    assert feedback.need_user_input is True
