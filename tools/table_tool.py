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

        anomalies = self._anomalies(dataframe)
        return {
            "message": "已完成表格分析",
            "table_analysis": True,
            "source": str(table_path),
            "row_count": int(dataframe.shape[0]),
            "column_count": int(dataframe.shape[1]),
            "missing_count": int(dataframe.isna().sum().sum()),
            "anomaly_count": len(anomalies),
            "columns": self._columns(dataframe),
            "anomalies": anomalies,
            "category_summaries": self._category_summaries(dataframe),
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
            if not is_numeric_dtype(series) or is_bool_dtype(series):
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
