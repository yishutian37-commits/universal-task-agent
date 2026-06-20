import pandas as pd
import pytest

from tools.table_tool import TableTool


def test_table_tool_analyzes_csv_file(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,warehouse,quantity,amount\n"
        "1,上海仓,10,100\n"
        "2,北京仓,,200\n"
        "3,上海仓,12,\n",
        encoding="utf-8",
    )

    result = TableTool().run(
        "analyze",
        {"previous_result": {"source": str(csv_path), "file_kind": "table"}},
    )

    assert result["message"] == "已完成表格分析"
    assert result["table_analysis"] is True
    assert result["row_count"] == 3
    assert result["column_count"] == 4
    assert result["missing_count"] == 2
    assert [column["name"] for column in result["columns"]] == [
        "order_id",
        "warehouse",
        "quantity",
        "amount",
    ]
    assert result["category_summaries"][0]["column"] == "warehouse"


def test_table_tool_analyzes_excel_file(tmp_path):
    xlsx_path = tmp_path / "orders.xlsx"
    pd.DataFrame(
        [
            {"order_id": 1, "warehouse": "上海仓", "quantity": 10},
            {"order_id": 2, "warehouse": "北京仓", "quantity": 12},
        ]
    ).to_excel(xlsx_path, index=False)

    result = TableTool().run(
        "analyze",
        {"previous_result": {"source": str(xlsx_path), "file_kind": "table"}},
    )

    assert result["row_count"] == 2
    assert result["column_count"] == 3
    assert result["missing_count"] == 0


def test_table_tool_detects_iqr_anomalies(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,quantity\n"
        "1,10\n"
        "2,11\n"
        "3,12\n"
        "4,13\n"
        "5,999\n",
        encoding="utf-8",
    )

    result = TableTool().run(
        "analyze",
        {"previous_result": {"source": str(csv_path), "file_kind": "table"}},
    )

    assert result["anomaly_count"] == 1
    assert result["anomalies"][0]["column"] == "quantity"
    assert result["anomalies"][0]["value"] == 999


def test_table_tool_raises_clear_error_without_table_path():
    with pytest.raises(ValueError, match="未找到可读取的 CSV 或 Excel 文件"):
        TableTool().run("analyze", {"user_input": "分析订单数据"})
