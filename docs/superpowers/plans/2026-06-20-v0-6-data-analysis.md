# UTA V0.6 Data Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0.6-data-analysis`, so UTA can read CSV/Excel files, analyze table structure and basic quality, generate a Markdown report, and verify report numbers against tool output.

**Architecture:** Keep the existing Planner -> Router -> Executor -> Verifier -> Reflection loop. Replace the stubbed `table_tool` with a focused pandas-based `TableTool`; extend `FileTool`, `ReportTool`, and `Verifier` only at their existing boundaries. Reports remain rule-generated in v0.6 so numerical claims are deterministic and easy to verify.

**Tech Stack:** Python 3.12, dataclasses, pytest, pandas, openpyxl, existing UTA tool registry and AgentState models.

---

## File Structure

- Modify `requirements.txt`: add `pandas` and `openpyxl`.
- Create `examples/orders.csv`: demo table for CLI smoke tests.
- Modify `tools/file_tool.py`: detect `.csv` / `.xlsx` paths and return table file metadata.
- Create `tools/table_tool.py`: read CSV/Excel and produce structured table statistics.
- Modify `tools/registry.py`: register real `TableTool`.
- Modify `tools/report_tool.py`: generate table analysis Markdown when previous result contains `table_analysis=True`.
- Modify `core/verifier.py`: verify table report sections, field coverage, and L1 number consistency.
- Modify `README.md` and `CHANGELOG.md`: document v0.6.
- Modify tests:
  - `tests/test_file_tool.py`
  - `tests/test_table_tool.py`
  - `tests/test_mock_tool.py`
  - `tests/test_report_tool.py`
  - `tests/test_verifier.py`
  - `tests/test_loop.py`
  - `tests/test_main.py`

---

### Task 1: Dependencies and Demo Data

**Files:**
- Modify: `requirements.txt`
- Create: `examples/orders.csv`

- [ ] **Step 1: Add dependencies**

Update `requirements.txt` to:

```text
pytest>=8.0.0
pandas>=2.0.0
openpyxl>=3.1.0
```

- [ ] **Step 2: Install dependencies locally**

Run:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Expected: command exits 0 and installs or confirms `pandas` and `openpyxl`.

- [ ] **Step 3: Add demo CSV**

Create `examples/orders.csv`:

```csv
order_id,warehouse,category,quantity,amount,status
1001,上海仓,电子配件,12,360,已出库
1002,上海仓,办公用品,5,125,已出库
1003,北京仓,电子配件,8,240,待拣货
1004,广州仓,耗材,30,450,已出库
1005,上海仓,耗材,,210,待拣货
1006,北京仓,办公用品,7,175,已出库
1007,广州仓,电子配件,10,300,已取消
1008,上海仓,电子配件,999,29970,已出库
1009,北京仓,耗材,18,,待拣货
1010,广州仓,办公用品,6,150,已出库
```

- [ ] **Step 4: Verify dependencies import**

Run:

```bash
.venv/bin/python -c "import pandas, openpyxl; print('ok')"
```

Expected output contains:

```text
ok
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt examples/orders.csv
git commit -m "chore: add data analysis dependencies"
```

---

### Task 2: FileTool Table Path Detection

**Files:**
- Modify: `tools/file_tool.py`
- Modify: `tests/test_file_tool.py`

- [ ] **Step 1: Write failing CSV path test**

Add to `tests/test_file_tool.py`:

```python
def test_file_tool_reads_csv_path_as_table_file(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("order_id,quantity\n1,2\n", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"分析 {csv_path}"})

    assert result["message"] == "已读取表格文件"
    assert result["source_type"] == "file"
    assert result["file_kind"] == "table"
    assert result["source"] == str(csv_path)
    assert "content" not in result
```

- [ ] **Step 2: Write failing Excel path test**

Add to `tests/test_file_tool.py`:

```python
def test_file_tool_reads_xlsx_path_as_table_file(tmp_path):
    xlsx_path = tmp_path / "orders.xlsx"
    xlsx_path.write_text("xlsx marker", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"分析 {xlsx_path}"})

    assert result["message"] == "已读取表格文件"
    assert result["file_kind"] == "table"
    assert result["source"] == str(xlsx_path)
```

- [ ] **Step 3: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_file_tool.py::test_file_tool_reads_csv_path_as_table_file tests/test_file_tool.py::test_file_tool_reads_xlsx_path_as_table_file -v
```

Expected: FAIL because `FileTool` currently ignores `.csv` / `.xlsx` paths.

- [ ] **Step 4: Implement table path detection**

Update `tools/file_tool.py`:

```python
from pathlib import Path
import re
from typing import Any

from tools.base_tool import BaseTool


TEXT_EXTENSIONS = (".txt", ".md")
TABLE_EXTENSIONS = (".csv", ".xlsx")


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read local text or table files for UTA tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = str(params.get("user_input", ""))
        file_path = self._find_existing_path(user_input)
        if file_path is None:
            return {
                "message": "已读取文本内容",
                "content": user_input,
                "source_type": "inline",
                "source": "user_input",
                "file_kind": "text",
            }

        if file_path.suffix.lower() in TABLE_EXTENSIONS:
            return {
                "message": "已读取表格文件",
                "source_type": "file",
                "source": str(file_path),
                "file_kind": "table",
            }

        content = file_path.read_text(encoding="utf-8")
        return {
            "message": "已读取文本内容",
            "content": content,
            "source_type": "file",
            "source": str(file_path),
            "file_kind": "text",
        }

    def _find_existing_path(self, text: str) -> Path | None:
        supported_extensions = TEXT_EXTENSIONS + TABLE_EXTENSIONS
        for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", text):
            path = Path(token).expanduser()
            if path.suffix.lower() not in supported_extensions:
                continue
            if path.exists() and path.is_file():
                return path
        return None
```

- [ ] **Step 5: Run green file tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_file_tool.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/file_tool.py tests/test_file_tool.py
git commit -m "feat: detect table files in file tool"
```

---

### Task 3: Real TableTool

**Files:**
- Create: `tools/table_tool.py`
- Modify: `tools/registry.py`
- Modify: `tests/test_table_tool.py`
- Modify: `tests/test_mock_tool.py`

- [ ] **Step 1: Write failing CSV analysis test**

Create `tests/test_table_tool.py`:

```python
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
```

- [ ] **Step 2: Write failing Excel analysis test**

Add to `tests/test_table_tool.py`:

```python
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
```

- [ ] **Step 3: Write failing anomaly test**

Add to `tests/test_table_tool.py`:

```python
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
```

- [ ] **Step 4: Write failing missing file test**

Add to `tests/test_table_tool.py`:

```python
def test_table_tool_raises_clear_error_without_table_path():
    with pytest.raises(ValueError, match="未找到可读取的 CSV 或 Excel 文件"):
        TableTool().run("analyze", {"user_input": "分析订单数据"})
```

- [ ] **Step 5: Update registry test expectation**

Modify `tests/test_mock_tool.py`:

```python
def test_registry_contains_summary_demo_tools():
    assert isinstance(TOOL_REGISTRY["mock_tool"], MockTool)
    assert TOOL_REGISTRY["file_tool"].name == "file_tool"
    assert TOOL_REGISTRY["text_tool"].name == "text_tool"
    assert TOOL_REGISTRY["table_tool"].name == "table_tool"
    assert TOOL_REGISTRY["report_tool"].name == "report_tool"
```

- [ ] **Step 6: Run red table tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_table_tool.py tests/test_mock_tool.py::test_registry_contains_summary_demo_tools -v
```

Expected: FAIL because `tools.table_tool` does not exist and registry still uses `PlaceholderTool`.

- [ ] **Step 7: Implement TableTool and registry**

Create `tools/table_tool.py`:

```python
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from tools.base_tool import BaseTool


TABLE_EXTENSIONS = (".csv", ".xlsx")


class TableTool(BaseTool):
    name = "table_tool"
    description = "Analyze local CSV or Excel tables."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        table_path = self._table_path(params)
        dataframe = self._read_table(table_path)
        if dataframe.empty:
            raise ValueError("表格为空，无法分析")

        columns = self._columns(dataframe)
        anomalies = self._anomalies(dataframe)
        category_summaries = self._category_summaries(dataframe)

        return {
            "message": "已完成表格分析",
            "table_analysis": True,
            "source": str(table_path),
            "row_count": int(dataframe.shape[0]),
            "column_count": int(dataframe.shape[1]),
            "missing_count": int(dataframe.isna().sum().sum()),
            "anomaly_count": len(anomalies),
            "columns": columns,
            "anomalies": anomalies,
            "category_summaries": category_summaries,
        }

    def _table_path(self, params: dict[str, Any]) -> Path:
        previous = params.get("previous_result")
        if isinstance(previous, dict):
            source = previous.get("source")
            if isinstance(source, str):
                path = self._existing_table_path(source)
                if path is not None:
                    return path

        user_input = str(params.get("user_input", ""))
        for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", user_input):
            path = self._existing_table_path(token)
            if path is not None:
                return path

        raise ValueError("未找到可读取的 CSV 或 Excel 文件")

    def _existing_table_path(self, text: str) -> Path | None:
        path = Path(text).expanduser()
        if path.suffix.lower() not in TABLE_EXTENSIONS:
            return None
        if not path.exists() or not path.is_file():
            return None
        return path

    def _read_table(self, path: Path) -> pd.DataFrame:
        try:
            if path.suffix.lower() == ".csv":
                return pd.read_csv(path)
            if path.suffix.lower() == ".xlsx":
                return pd.read_excel(path)
        except Exception as exc:
            raise ValueError(f"读取表格失败：{exc}") from exc
        raise ValueError("仅支持 .csv / .xlsx")

    def _columns(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "name": str(column),
                "dtype": str(dataframe[column].dtype),
                "non_null_count": int(dataframe[column].notna().sum()),
                "missing_count": int(dataframe[column].isna().sum()),
            }
            for column in dataframe.columns
        ]

    def _anomalies(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        anomalies = []
        for column in dataframe.columns:
            series = dataframe[column]
            if not is_numeric_dtype(series):
                continue
            numbers = series.dropna()
            if len(numbers) < 4:
                continue
            q1 = numbers.quantile(0.25)
            q3 = numbers.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)]
            for row_index, value in outliers.items():
                anomalies.append(
                    {
                        "column": str(column),
                        "row_number": int(row_index) + 1,
                        "value": self._json_value(value),
                        "reason": "IQR 异常值",
                    }
                )
        return anomalies

    def _category_summaries(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        summaries = []
        for column in dataframe.columns:
            series = dataframe[column]
            if is_numeric_dtype(series) and not is_bool_dtype(series):
                continue
            counts = series.dropna().value_counts().head(5)
            if counts.empty:
                continue
            summaries.append(
                {
                    "column": str(column),
                    "top_values": [
                        {"value": str(value), "count": int(count)}
                        for value, count in counts.items()
                    ],
                }
            )
        return summaries

    def _json_value(self, value: Any) -> Any:
        if hasattr(value, "item"):
            return value.item()
        return value
```

Update `tools/registry.py`:

```python
from tools.file_tool import FileTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": FileTool(),
    "text_tool": TextTool(),
    "table_tool": TableTool(),
    "report_tool": ReportTool(),
}
```

- [ ] **Step 8: Run green table tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_table_tool.py tests/test_mock_tool.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/table_tool.py tools/registry.py tests/test_table_tool.py tests/test_mock_tool.py
git commit -m "feat: add table analysis tool"
```

---

### Task 4: Table Report Output

**Files:**
- Modify: `tools/report_tool.py`
- Modify: `tests/test_report_tool.py`

- [ ] **Step 1: Write failing table report test**

Add to `tests/test_report_tool.py`:

```python
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
```

- [ ] **Step 2: Write failing anomaly report test**

Add to `tests/test_report_tool.py`:

```python
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
```

- [ ] **Step 3: Run red report tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_report_tool.py::test_report_tool_generates_table_analysis_report tests/test_report_tool.py::test_report_tool_lists_table_anomalies -v
```

Expected: FAIL because `ReportTool` does not generate table reports yet.

- [ ] **Step 4: Implement table report generation**

Update `tools/report_tool.py`:

```python
from typing import Any

from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Return the final Markdown report for UTA tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        previous = params.get("previous_result")
        if isinstance(previous, dict) and previous.get("table_analysis") is True:
            report = self._table_report(previous)
            return {"message": report, "report_markdown": report}

        summary = ""
        if isinstance(previous, dict) and isinstance(previous.get("summary_markdown"), str):
            summary = previous["summary_markdown"].strip()
        if not summary:
            summary = "未生成总结报告"
        return {
            "message": summary,
            "report_markdown": summary,
        }

    def _table_report(self, analysis: dict[str, Any]) -> str:
        return "\n\n".join(
            [
                self._field_section(analysis),
                self._stats_section(analysis),
                self._anomaly_section(analysis),
                self._category_section(analysis),
                self._business_section(analysis),
                self._next_steps_section(analysis),
            ]
        )

    def _field_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 字段说明"]
        for column in analysis.get("columns", []):
            lines.append(
                f"- {column['name']}：类型 {column['dtype']}，非空 {column['non_null_count']}，缺失 {column['missing_count']}"
            )
        return "\n".join(lines)

    def _stats_section(self, analysis: dict[str, Any]) -> str:
        return "\n".join(
            [
                "## 基础统计",
                f"- 行数：{analysis.get('row_count', 0)}",
                f"- 列数：{analysis.get('column_count', 0)}",
                f"- 缺失值数量：{analysis.get('missing_count', 0)}",
                f"- 异常值数量：{analysis.get('anomaly_count', 0)}",
            ]
        )

    def _anomaly_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 异常数据"]
        anomalies = analysis.get("anomalies", [])
        if not anomalies:
            lines.append("未检测到异常")
            return "\n".join(lines)
        for anomaly in anomalies:
            lines.append(
                f"- 第 {anomaly['row_number']} 行，字段 {anomaly['column']}，值 {anomaly['value']}：{anomaly['reason']}"
            )
        return "\n".join(lines)

    def _category_section(self, analysis: dict[str, Any]) -> str:
        lines = ["## 分类汇总"]
        summaries = analysis.get("category_summaries", [])
        if not summaries:
            lines.append("未发现可汇总的分类字段")
            return "\n".join(lines)
        for summary in summaries:
            values = "，".join(
                f"{item['value']} {item['count']} 条"
                for item in summary.get("top_values", [])
            )
            lines.append(f"- {summary['column']}：{values}")
        return "\n".join(lines)

    def _business_section(self, analysis: dict[str, Any]) -> str:
        missing = analysis.get("missing_count", 0)
        anomalies = analysis.get("anomaly_count", 0)
        if missing or anomalies:
            return "\n".join(
                [
                    "## 业务解释",
                    "表格存在需要关注的数据质量问题，建议先处理缺失值和异常值，再用于业务决策。",
                ]
            )
        return "\n".join(
            [
                "## 业务解释",
                "表格基础质量较稳定，可用于后续分类汇总和业务复盘。",
            ]
        )

    def _next_steps_section(self, analysis: dict[str, Any]) -> str:
        del analysis
        return "\n".join(
            [
                "## 后续建议",
                "- 核对缺失值来源",
                "- 复查异常值是否为真实业务峰值",
                "- 按关键分类字段继续做分组分析",
            ]
        )
```

- [ ] **Step 5: Run green report tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_report_tool.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/report_tool.py tests/test_report_tool.py
git commit -m "feat: generate table analysis reports"
```

---

### Task 5: Verifier Table Report Checks

**Files:**
- Modify: `core/verifier.py`
- Modify: `tests/test_verifier.py`

- [ ] **Step 1: Write failing complete table report test**

Add to `tests/test_verifier.py`:

```python
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
```

- [ ] **Step 2: Write failing missing field test**

Add to `tests/test_verifier.py`:

```python
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
```

- [ ] **Step 3: Write failing mismatched table number test**

Add to `tests/test_verifier.py`:

```python
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
```

- [ ] **Step 4: Write failing no-anomaly wording test**

Add to `tests/test_verifier.py`:

```python
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
```

- [ ] **Step 5: Run red verifier tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_verifier.py::test_verifier_passes_complete_table_analysis_report tests/test_verifier.py::test_verifier_fails_table_report_missing_field_name tests/test_verifier.py::test_verifier_fails_table_report_mismatched_numbers tests/test_verifier.py::test_verifier_fails_table_report_without_no_anomaly_wording -v
```

Expected: FAIL because table report verification is not implemented.

- [ ] **Step 6: Attach source stats in ReportTool**

Before implementing the verifier, update `ReportTool.run()` table branch so result includes source stats:

```python
if isinstance(previous, dict) and previous.get("table_analysis") is True:
    report = self._table_report(previous)
    return {
        "message": report,
        "report_markdown": report,
        "source_table_stats": previous,
    }
```

- [ ] **Step 7: Implement table report verification**

Update `core/verifier.py` by adding table sections and routing:

```python
TABLE_REQUIRED_SECTIONS = ["字段说明", "基础统计", "异常数据"]
```

In `check()` after summary check:

```python
if self._should_check_table_report(state, result):
    return self._check_table_report(result)
```

Add methods:

```python
def _should_check_table_report(self, state: AgentState | None, result: ToolResult) -> bool:
    return (
        state is not None
        and state.task_type == "data_analysis"
        and result.tool_name == "report_tool"
    )

def _check_table_report(self, result: ToolResult) -> CheckResult:
    report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
    source_stats = result.result.get("source_table_stats") or {}
    failed_reasons = []
    suggested_fix = []

    for section in TABLE_REQUIRED_SECTIONS:
        content = self._section_content(report_text, section, TABLE_REQUIRED_SECTIONS + ["分类汇总", "业务解释", "后续建议"])
        if content is None:
            failed_reasons.append(f"缺少必要小节：{section}")
            suggested_fix.append(f"补齐{section}小节")
        elif not content.strip():
            failed_reasons.append(f"小节内容为空：{section}")
            suggested_fix.append(f"补充{section}小节内容")

    field_section = self._section_content(report_text, "字段说明", TABLE_REQUIRED_SECTIONS + ["分类汇总", "业务解释", "后续建议"]) or ""
    for column in source_stats.get("columns", []):
        column_name = str(column.get("name", ""))
        if column_name and column_name not in field_section:
            failed_reasons.append(f"字段说明缺少字段：{column_name}")
            suggested_fix.append(f"补充字段说明：{column_name}")

    number_check = self.check_table_numbers(report_text, source_stats)
    failed_reasons.extend(number_check.failed_reasons)
    suggested_fix.extend(number_check.suggested_fix)

    if source_stats.get("anomaly_count") == 0 and "未检测到异常" not in report_text:
        failed_reasons.append("未检测到异常时必须写明：未检测到异常")
        suggested_fix.append("在异常数据小节写明：未检测到异常")

    return CheckResult(
        passed=not failed_reasons,
        failed_reasons=failed_reasons,
        suggested_fix=suggested_fix,
    )
```

Refactor `_section_content()` to accept headings:

```python
def _section_content(
    self,
    report_text: str,
    section: str,
    all_headings: list[str] | None = None,
) -> str | None:
    headings_source = all_headings or SUMMARY_REQUIRED_SECTIONS + ["关键事实", "待办事项"]
    headings = "|".join(re.escape(item) for item in headings_source)
    pattern = re.compile(
        rf"(?:^|\n)[ \t]*(?:#+[ \t]*)?{re.escape(section)}[ \t]*[：:]?[ \t]*\n?"
        rf"(.*?)(?=\n[ \t]*(?:#+[ \t]*)?(?:{headings})[ \t]*[：:]?[ \t]*\n?|\Z)",
        re.DOTALL,
    )
    match = pattern.search(report_text)
    if not match:
        return None
    return match.group(1).strip()
```

- [ ] **Step 8: Run green verifier and report tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_verifier.py tests/test_report_tool.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/verifier.py tools/report_tool.py tests/test_verifier.py tests/test_report_tool.py
git commit -m "feat: verify table analysis reports"
```

---

### Task 6: End-to-End Data Analysis Flow and Docs

**Files:**
- Modify: `tests/test_loop.py`
- Modify: `tests/test_main.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write failing loop test for data analysis**

Add to `tests/test_loop.py`:

```python
def test_loop_executes_data_analysis_flow(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,warehouse,quantity\n"
        "1,上海仓,10\n"
        "2,北京仓,\n"
        "3,上海仓,12\n",
        encoding="utf-8",
    )
    state = AgentState(
        task_id="task_test",
        user_input=f"分析 {csv_path}",
        task_type="data_analysis",
        intent="analyze_table",
    )

    updated = run_minimal_loop(state)

    assert updated.status == "completed"
    assert updated.results[0].tool_name == "file_tool"
    assert updated.results[1].tool_name == "table_tool"
    assert updated.results[2].tool_name == "report_tool"
    assert "## 字段说明" in updated.final_output
    assert "行数：3" in updated.final_output
    assert "缺失值数量：1" in updated.final_output
```

- [ ] **Step 2: Write failing main integration test**

Add to `tests/test_main.py`:

```python
def test_run_task_outputs_data_analysis_report(tmp_path, monkeypatch):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,warehouse,quantity\n"
        "1,上海仓,10\n"
        "2,北京仓,\n"
        "3,上海仓,12\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    state = run_task(f"分析 {csv_path}", output_dir=tmp_path / ".agents")

    assert state.status == "completed"
    assert "## 字段说明" in state.final_output
    assert "行数：3" in state.final_output
    assert (tmp_path / ".agents" / f"{state.task_id}_state.json").exists()
```

- [ ] **Step 3: Run red end-to-end tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_loop.py::test_loop_executes_data_analysis_flow tests/test_main.py::test_run_task_outputs_data_analysis_report -v
```

Expected: PASS if previous tasks wired correctly, or FAIL with a concrete routing/report/verifier bug that must be fixed before proceeding.

- [ ] **Step 4: Update docs**

Update README current milestone:

```markdown
UTA 是一个学习型 Agent 框架。当前里程碑是 `v0.6-data-analysis`：在总结链路之外，新增 CSV / Excel 表格分析工具、Markdown 表格报告和数字一致性校验。
```

Update README current status list:

```markdown
- `v0.6-data-analysis`: `table_tool` 读取 CSV / Excel，生成字段、基础统计、缺失值、异常值和分类汇总，并由 `Verifier` 做表格报告校验。
```

Add README usage example:

```markdown
## 表格分析示例

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```
```

Update `CHANGELOG.md` under `Unreleased`:

```markdown
- Add `v0.6-data-analysis` with CSV/Excel table analysis, table reports, and numeric verification.
```

- [ ] **Step 5: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run CLI smoke test**

Run:

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

Expected: exits 0 and prints `任务已完成：` followed by Markdown containing `## 字段说明`, `## 基础统计`, and `## 异常数据`.

- [ ] **Step 7: Commit docs and integration**

```bash
git add tests/test_loop.py tests/test_main.py README.md CHANGELOG.md
git commit -m "docs: document data analysis flow"
```

---

### Task 7: Final Verification and Tag

**Files:**
- No source changes expected.

- [ ] **Step 1: Run full tests again**

Run:

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run CLI demo again**

Run:

```bash
.venv/bin/python main.py --task "分析 examples/orders.csv"
```

Expected: output contains `任务已完成：`, `## 字段说明`, `行数：10`, `列数：6`, and `异常数据`.

- [ ] **Step 3: Check status and secrets**

Run:

```bash
git status --short
git grep -n -E 'tp-[[:alnum:]]{20,}'
```

Expected: `git status --short` shows only unrelated pre-existing untracked files, or is clean. `git grep` exits 1 with no output.

- [ ] **Step 4: Tag v0.6**

Run:

```bash
git tag v0.6-data-analysis
git tag --list "v0.6-data-analysis"
```

Expected output:

```text
v0.6-data-analysis
```

---

## Self-Review

- Spec coverage: covers CSV and Excel reading, real `table_tool`, table Markdown reports, Verifier field/number checks, example data, docs, tests, and tag.
- Scope check: excludes charts, external databases, LLM business interpretation, Memory, Skill, TAM, and complete replan.
- Type consistency: uses existing `BaseTool.run(action_name, params)`, `ToolResult.result`, `AgentState.task_type`, `ReportTool` output shape, and existing `Verifier.check(state, step, result)`.
- TDD check: every production behavior change has a failing test step before implementation.
