from typing import Any

from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Return the final Markdown report for UTA tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        previous = params.get("previous_result")
        if isinstance(previous, dict) and "search_results" in previous:
            report = self._research_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_search_results": previous.get("search_results", []),
            }
        if isinstance(previous, dict) and previous.get("table_analysis") is True:
            report = self._table_report(previous)
            return {
                "message": report,
                "report_markdown": report,
                "source_table_stats": previous,
            }

        summary = ""
        if isinstance(previous, dict) and isinstance(previous.get("summary_markdown"), str):
            summary = previous["summary_markdown"].strip()
        if not summary:
            summary = "未生成总结报告"
        return {
            "message": summary,
            "report_markdown": summary,
        }

    def _research_report(self, search_payload: dict[str, Any]) -> str:
        query = str(search_payload.get("query") or "调研主题")
        results = search_payload.get("search_results") or []
        if not results:
            return "\n\n".join(
                [
                    "## 结论\n未找到可用来源。",
                    "## 关键发现\n- 未找到可用来源。",
                    "## 来源\n未找到可用来源。",
                    "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
                ]
            )

        findings = "\n".join(
            f"- {item.get('snippet') or item.get('title') or '搜索结果未提供摘要'}"
            for item in results
        )
        sources = "\n".join(
            f"- [{item.get('title') or item.get('url')}]({item.get('url')}): {item.get('snippet') or '无摘要'}"
            for item in results
            if item.get("url")
        )
        return "\n\n".join(
            [
                f"## 结论\n基于当前搜索结果，{query} 可以先形成一份初步调研结论。",
                f"## 关键发现\n{findings}",
                f"## 来源\n{sources}",
                "## 注意事项\n当前报告只基于搜索摘要，不等同于阅读全文后的事实核验。",
            ]
        )

    def _table_report(self, analysis: dict[str, Any]) -> str:
        return "\n\n".join(
            [
                self._field_section(analysis),
                self._stats_section(analysis),
                self._anomaly_section(analysis),
                self._category_section(analysis),
                self._business_section(analysis),
                self._next_steps_section(),
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

    def _next_steps_section(self) -> str:
        return "\n".join(
            [
                "## 后续建议",
                "- 核对缺失值来源",
                "- 复查异常值是否为真实业务峰值",
                "- 按关键分类字段继续做分组分析",
            ]
        )
