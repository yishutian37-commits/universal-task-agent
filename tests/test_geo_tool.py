from tools.geo_tool import GeoTool


def test_geo_tool_generates_matrix_brief_and_compliance():
    result = GeoTool(vendor_root="skills/vendor/geo-agent-marketing-optimized").run(
        "analyze",
        {
            "user_input": (
                "帮我做 GEO 分析：行业是本地装修，地区是包头，"
                "品牌事实：有官网、提供设计和施工服务、需要避免夸大承诺。"
            )
        },
    )

    assert result["message"] == "已完成 GEO 分析"
    assert result["geo_analysis"] is True
    assert result["industry"] == "本地装修"
    assert result["region"] == "包头"
    assert "价格" in result["fact_gaps"]
    assert len(result["question_matrix"]) == 4
    assert {item["layer"] for item in result["question_matrix"]} == {
        "pool_layer",
        "verification_layer",
        "authority_layer",
        "conversion_layer",
    }
    assert result["question_matrix"][0]["question"] == "包头本地装修哪家靠谱？"
    assert result["content_briefs"][0]["target_question"] == "包头本地装修哪家靠谱？"
    assert result["compliance_checks"][0]["level"] == "warning"
    assert "question-matrix-contract.md" in result["vendor_rules"]["question_matrix_contract"]


def test_geo_tool_uses_safe_defaults_when_input_is_sparse():
    result = GeoTool(vendor_root="skills/vendor/geo-agent-marketing-optimized").run(
        "analyze",
        {"user_input": "做一个 GEO 问题矩阵"},
    )

    assert result["industry"] == "未提供行业"
    assert result["region"] == "未提供地区"
    assert result["brand_facts"] == []
    assert result["question_matrix"][0]["question"] == "未提供地区未提供行业哪家靠谱？"
