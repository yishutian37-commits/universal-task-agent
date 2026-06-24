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


def test_report_tool_handles_empty_research_results():
    result = ReportTool().run(
        "generate",
        {"previous_result": {"query": "不存在的主题", "search_results": []}},
    )

    assert "未找到可用来源" in result["report_markdown"]
    assert result["source_search_results"] == []
