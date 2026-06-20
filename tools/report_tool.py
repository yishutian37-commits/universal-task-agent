from typing import Any

from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Return the final Markdown report for summary tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        previous = params.get("previous_result")
        summary = ""
        if isinstance(previous, dict) and isinstance(previous.get("summary_markdown"), str):
            summary = previous["summary_markdown"].strip()
        if not summary:
            summary = "未生成总结报告"
        return {
            "message": summary,
            "report_markdown": summary,
        }
