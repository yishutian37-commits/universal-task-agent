from tools.report_tool import ReportTool


TABLE_ANALYSIS = {
    "message": "已完成表格分析",
    "table_analysis": True,
    "source": "orders.csv",
    "row_count": 3,
    "column_count": 3,
    "missing_count": 1,
    "anomaly_count": 0,
    "columns": [
        {"name": "order_id", "dtype": "int64", "non_null_count": 3, "missing_count": 0},
        {"name": "warehouse", "dtype": "object", "non_null_count": 3, "missing_count": 0},
        {"name": "quantity", "dtype": "float64", "non_null_count": 2, "missing_count": 1},
    ],
    "anomalies": [],
    "category_summaries": [
        {
            "column": "warehouse",
            "top_values": [
                {"value": "上海仓", "count": 2},
                {"value": "北京仓", "count": 1},
            ],
        }
    ],
}

CODE_ANALYSIS = {
    "message": "已完成 UTA 代码链路扫描",
    "code_analysis": True,
    "project_root": "/tmp/uta",
    "focus": "task_flow",
    "required_files": ["main.py", "core/loop.py", "core/router.py", "core/verifier.py"],
    "files": [
        {
            "path": "main.py",
            "role": "CLI 入口与任务运行编排",
            "imports": ["argparse", "core.loop.run_minimal_loop"],
            "classes": [],
            "functions": ["run_task", "main"],
        },
        {
            "path": "core/loop.py",
            "role": "Agent 主循环、重试、反思和 replan 控制",
            "imports": ["core.executor.Executor"],
            "classes": [],
            "functions": ["run_minimal_loop"],
        },
        {
            "path": "core/router.py",
            "role": "根据步骤目标选择工具",
            "imports": ["core.state.Action"],
            "classes": ["Router"],
            "functions": [],
        },
        {
            "path": "core/verifier.py",
            "role": "用硬规则校验工具结果和最终报告",
            "imports": ["re"],
            "classes": ["Verifier"],
            "functions": [],
        },
    ],
}


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


def test_report_tool_generates_table_analysis_report():
    result = ReportTool().run("generate", {"previous_result": TABLE_ANALYSIS})

    report = result["report_markdown"]

    assert result["message"] == report
    assert "## 字段说明" in report
    assert "order_id" in report
    assert "warehouse" in report
    assert "quantity" in report
    assert "## 基础统计" in report
    assert "行数：3" in report
    assert "列数：3" in report
    assert "缺失值数量：1" in report
    assert "异常值数量：0" in report
    assert "## 异常数据" in report
    assert "未检测到异常" in report
    assert "## 分类汇总" in report
    assert "## 业务解释" in report
    assert "## 后续建议" in report


def test_report_tool_lists_table_anomalies():
    analysis = dict(TABLE_ANALYSIS)
    analysis["anomaly_count"] = 1
    analysis["anomalies"] = [
        {"column": "quantity", "row_number": 5, "value": 999, "reason": "IQR 异常值"}
    ]

    report = ReportTool().run("generate", {"previous_result": analysis})["report_markdown"]

    assert "异常值数量：1" in report
    assert "quantity" in report
    assert "999" in report
    assert "IQR 异常值" in report


def test_report_tool_generates_research_report_with_sources():
    result = ReportTool().run(
        "generate",
        {
            "previous_result": {
                "query": "UTA Agent",
                "search_results": [
                    {
                        "title": "UTA 路线",
                        "url": "https://example.com/uta",
                        "snippet": "UTA 应先跑通核心 Agent Loop。",
                        "source": "fixture",
                    }
                ],
            }
        },
    )

    report = result["report_markdown"]

    assert "## 结论" in report
    assert "## 关键发现" in report
    assert "## 来源" in report
    assert "## 注意事项" in report
    assert "[UTA 路线](https://example.com/uta)" in report
    assert result["source_search_results"][0]["url"] == "https://example.com/uta"


def test_report_tool_generates_code_reading_report():
    result = ReportTool().run("generate", {"previous_result": CODE_ANALYSIS})

    report = result["report_markdown"]

    assert result["message"] == report
    assert result["source_code_analysis"] == CODE_ANALYSIS
    for section in ["任务链路", "关键文件", "模块职责", "调用顺序", "状态与记忆", "桌面端入口", "风险点", "下一步建议"]:
        assert f"## {section}" in report
    assert "main.py" in report
    assert "core/loop.py" in report
    assert "core/router.py" in report
    assert "core/verifier.py" in report


def test_report_tool_generates_weather_report():
    result = ReportTool().run(
        "generate",
        {
            "previous_result": {
                "query": "包头今日天气状况",
                "weather_result": {
                    "city": "包头",
                    "provider": "fake-weather",
                    "source_url": "https://example.com/weather",
                    "time": "2026-06-24T14:00",
                    "weather_text": "晴",
                    "temperature": 23.4,
                    "apparent_temperature": 22.8,
                    "relative_humidity": 41,
                    "precipitation": 0,
                    "wind_speed": 12.5,
                    "wind_direction": 270,
                },
                "search_results": [
                    {
                        "title": "包头 今日天气",
                        "url": "https://example.com/weather",
                        "snippet": "包头当前晴，气温 23.4℃。",
                        "source": "fake-weather",
                    }
                ],
            }
        },
    )

    report = result["report_markdown"]

    assert "## 结论" in report
    assert "包头当前天气：晴" in report
    assert "气温：23.4℃" in report
    assert "体感温度：22.8℃" in report
    assert "湿度：41%" in report
    assert "降水量：0 mm" in report
    assert "[fake-weather](https://example.com/weather)" in report
    assert "不是普通网页搜索摘要" in report
    assert result["source_weather"] == {
        "city": "包头",
        "provider": "fake-weather",
        "source_url": "https://example.com/weather",
        "time": "2026-06-24T14:00",
        "weather_text": "晴",
        "temperature": 23.4,
        "apparent_temperature": 22.8,
        "relative_humidity": 41,
        "precipitation": 0,
        "wind_speed": 12.5,
        "wind_direction": 270,
    }


def test_report_tool_handles_empty_research_results():
    result = ReportTool().run(
        "generate",
        {"previous_result": {"query": "不存在的主题", "search_results": []}},
    )

    assert "未找到可用来源" in result["report_markdown"]
    assert result["source_search_results"] == []
