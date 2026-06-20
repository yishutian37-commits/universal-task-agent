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


def test_verifier_passes_matching_table_numbers():
    check = Verifier().check_table_numbers(
        "基础统计：行数 10，列数 3，缺失值数量 2，异常值数量 0。",
        {"row_count": 10, "column_count": 3, "missing_count": 2, "anomaly_count": 0},
    )

    assert check.passed is True


def test_verifier_fails_mismatched_table_numbers():
    check = Verifier().check_table_numbers(
        "基础统计：行数 9，列数 3，缺失值数量 2，异常值数量 0。",
        {"row_count": 10, "column_count": 3, "missing_count": 2, "anomaly_count": 0},
    )

    assert check.passed is False
    assert "行数不一致：报告=9，工具=10" in check.failed_reasons


def test_verifier_passes_complete_table_analysis_report():
    state = AgentState(task_id="task_test", user_input="分析表格", task_type="data_analysis")
    step = PlanStep(step_id=3, goal="生成表格分析报告")
    result = ToolResult(
        True,
        "report_tool",
        "generate",
        {
            "message": (
                "## 字段说明\n"
                "- order_id：类型 int64\n"
                "- warehouse：类型 object\n"
                "## 基础统计\n"
                "- 行数：3\n"
                "- 列数：2\n"
                "- 缺失值数量：0\n"
                "- 异常值数量：0\n"
                "## 异常数据\n"
                "未检测到异常"
            ),
            "source_table_stats": {
                "row_count": 3,
                "column_count": 2,
                "missing_count": 0,
                "anomaly_count": 0,
                "columns": [{"name": "order_id"}, {"name": "warehouse"}],
            },
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is True


def test_verifier_fails_table_report_missing_field_name():
    state = AgentState(task_id="task_test", user_input="分析表格", task_type="data_analysis")
    step = PlanStep(step_id=3, goal="生成表格分析报告")
    result = ToolResult(
        True,
        "report_tool",
        "generate",
        {
            "message": (
                "## 字段说明\n"
                "- order_id：类型 int64\n"
                "## 基础统计\n"
                "- 行数：3\n"
                "- 列数：2\n"
                "- 缺失值数量：0\n"
                "- 异常值数量：0\n"
                "## 异常数据\n"
                "未检测到异常"
            ),
            "source_table_stats": {
                "row_count": 3,
                "column_count": 2,
                "missing_count": 0,
                "anomaly_count": 0,
                "columns": [{"name": "order_id"}, {"name": "warehouse"}],
            },
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "字段说明缺少字段：warehouse" in check.failed_reasons


def test_verifier_fails_table_report_mismatched_numbers():
    state = AgentState(task_id="task_test", user_input="分析表格", task_type="data_analysis")
    step = PlanStep(step_id=3, goal="生成表格分析报告")
    result = ToolResult(
        True,
        "report_tool",
        "generate",
        {
            "message": (
                "## 字段说明\n"
                "- order_id：类型 int64\n"
                "## 基础统计\n"
                "- 行数：99\n"
                "- 列数：1\n"
                "- 缺失值数量：0\n"
                "- 异常值数量：0\n"
                "## 异常数据\n"
                "未检测到异常"
            ),
            "source_table_stats": {
                "row_count": 3,
                "column_count": 1,
                "missing_count": 0,
                "anomaly_count": 0,
                "columns": [{"name": "order_id"}],
            },
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "行数不一致：报告=99，工具=3" in check.failed_reasons


def test_verifier_fails_table_report_without_no_anomaly_wording():
    state = AgentState(task_id="task_test", user_input="分析表格", task_type="data_analysis")
    step = PlanStep(step_id=3, goal="生成表格分析报告")
    result = ToolResult(
        True,
        "report_tool",
        "generate",
        {
            "message": (
                "## 字段说明\n"
                "- order_id：类型 int64\n"
                "## 基础统计\n"
                "- 行数：3\n"
                "- 列数：1\n"
                "- 缺失值数量：0\n"
                "- 异常值数量：0\n"
                "## 异常数据\n"
                "暂无"
            ),
            "source_table_stats": {
                "row_count": 3,
                "column_count": 1,
                "missing_count": 0,
                "anomaly_count": 0,
                "columns": [{"name": "order_id"}],
            },
        },
    )

    check = Verifier().check(state, step, result)

    assert check.passed is False
    assert "未检测到异常时必须写明：未检测到异常" in check.failed_reasons
