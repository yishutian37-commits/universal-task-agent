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


def test_verifier_accepts_research_report_with_sources():
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n初步结论。\n\n"
                "## 关键发现\n- 发现一。\n\n"
                "## 来源\n- [来源](https://example.com/uta)：摘要\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [{"url": "https://example.com/uta"}],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is True


def test_verifier_rejects_research_report_missing_source_url():
    state = AgentState(
        task_id="task_test",
        user_input="调研 UTA",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n初步结论。\n\n"
                "## 关键发现\n- 发现一。\n\n"
                "## 来源\n- 来源缺少链接\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [{"url": "https://example.com/uta"}],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is False
    assert "来源缺少 URL：https://example.com/uta" in check.failed_reasons


def test_verifier_accepts_empty_research_report_when_no_sources_available():
    state = AgentState(
        task_id="task_test",
        user_input="调研 不存在的主题",
        task_type="research",
        intent="research_topic",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 结论\n未找到可用来源。\n\n"
                "## 关键发现\n- 未找到可用来源。\n\n"
                "## 来源\n未找到可用来源。\n\n"
                "## 注意事项\n当前报告只基于搜索摘要。"
            ),
            "source_search_results": [],
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成带来源的调研报告"), result)

    assert check.passed is True


def test_verifier_accepts_complete_code_reading_report():
    state = AgentState(
        task_id="task_test",
        user_input="阅读 UTA 代码",
        task_type="code_reading",
        intent="read_task_flow",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 任务链路\n一次任务从 main.run_task 开始。\n\n"
                "## 关键文件\n- `main.py`\n- `core/loop.py`\n- `core/router.py`\n- `core/verifier.py`\n\n"
                "## 模块职责\n各模块职责清晰。\n\n"
                "## 调用顺序\n1. main.py\n2. core/loop.py\n\n"
                "## 状态与记忆\nAgentState 保存短期状态。\n\n"
                "## 桌面端入口\ndesktop.api 调用 runner。\n\n"
                "## 风险点\n只读扫描，不修改代码。\n\n"
                "## 下一步建议\n增加更丰富的依赖图。"
            ),
            "source_code_analysis": {
                "files": [
                    {"path": "main.py"},
                    {"path": "core/loop.py"},
                    {"path": "core/router.py"},
                    {"path": "core/verifier.py"},
                ]
            },
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成代码阅读报告"), result)

    assert check.passed is True


def test_verifier_rejects_code_report_missing_required_file():
    state = AgentState(
        task_id="task_test",
        user_input="阅读 UTA 代码",
        task_type="code_reading",
        intent="read_task_flow",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 任务链路\n一次任务从 main.run_task 开始。\n\n"
                "## 关键文件\n- `main.py`\n- `core/loop.py`\n- `core/router.py`\n\n"
                "## 模块职责\n各模块职责清晰。\n\n"
                "## 调用顺序\n1. main.py\n2. core/loop.py\n\n"
                "## 状态与记忆\nAgentState 保存短期状态。\n\n"
                "## 桌面端入口\ndesktop.api 调用 runner。\n\n"
                "## 风险点\n只读扫描，不修改代码。\n\n"
                "## 下一步建议\n增加更丰富的依赖图。"
            ),
            "source_code_analysis": {
                "files": [
                    {"path": "main.py"},
                    {"path": "core/loop.py"},
                    {"path": "core/router.py"},
                ]
            },
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成代码阅读报告"), result)

    assert check.passed is False
    assert "扫描结果缺少关键文件：core/verifier.py" in check.failed_reasons
    assert "关键文件小节缺少文件：core/verifier.py" in check.failed_reasons


def test_verifier_accepts_complete_geo_report():
    state = AgentState(
        task_id="task_test",
        user_input="做 GEO 分析",
        task_type="geo_analysis",
        intent="geo_analysis",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 事实输入\n行业：本地装修；地区：包头。\n\n"
                "## 事实缺口\n- 价格\n\n"
                "## 问题矩阵\n- 包头本地装修哪家靠谱？（pool_layer，本地推荐）\n\n"
                "## 内容Brief\n- 公众号 × 品牌介绍：包头本地装修哪家靠谱？\n\n"
                "## 平台合规\n- warning：避免夸大承诺。\n\n"
                "## 规则来源\n- question-matrix-contract.md\n\n"
                "## 下一步建议\n- 补齐价格和案例事实。"
            ),
            "source_geo_analysis": {
                "geo_analysis": True,
                "question_matrix": [{"question": "包头本地装修哪家靠谱？"}],
            },
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成 GEO 分析报告"), result)

    assert check.passed is True


def test_verifier_rejects_geo_report_without_matrix_question():
    state = AgentState(
        task_id="task_test",
        user_input="做 GEO 分析",
        task_type="geo_analysis",
        intent="geo_analysis",
    )
    result = ToolResult(
        success=True,
        tool_name="report_tool",
        action_name="generate",
        result={
            "message": (
                "## 事实输入\n行业：本地装修；地区：包头。\n\n"
                "## 事实缺口\n- 价格\n\n"
                "## 问题矩阵\n- 缺少真实问题。\n\n"
                "## 内容Brief\n- 公众号 × 品牌介绍。\n\n"
                "## 平台合规\n- warning：避免夸大承诺。\n\n"
                "## 规则来源\n- question-matrix-contract.md\n\n"
                "## 下一步建议\n- 补齐价格和案例事实。"
            ),
            "source_geo_analysis": {
                "geo_analysis": True,
                "question_matrix": [{"question": "包头本地装修哪家靠谱？"}],
            },
        },
    )

    check = Verifier().check(state, PlanStep(step_id=2, goal="生成 GEO 分析报告"), result)

    assert check.passed is False
    assert "问题矩阵小节缺少问题：包头本地装修哪家靠谱？" in check.failed_reasons
