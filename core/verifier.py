import re

from core.state import AgentState, CheckResult, PlanStep, ToolResult


SUMMARY_REQUIRED_SECTIONS = ["摘要", "核心观点", "风险点"]
TABLE_REQUIRED_SECTIONS = ["字段说明", "基础统计", "异常数据"]
RESEARCH_REQUIRED_SECTIONS = ["结论", "关键发现", "来源", "注意事项"]


class Verifier:
    def check(self, *args) -> CheckResult:
        if len(args) == 1:
            state = None
            result = args[0]
        elif len(args) == 3:
            state, _step, result = args
        else:
            raise TypeError("Verifier.check expects result or state, step, result")

        if not result.success:
            return self._failed_tool_check(result)

        if self._should_check_summary(state, result):
            return self._check_summary(result)

        if self._should_check_research_report(state, result):
            return self._check_research_report(result)

        if self._should_check_table_report(state, result):
            return self._check_table_report(result)

        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    def _failed_tool_check(self, result: ToolResult) -> CheckResult:
        error = result.error or "unknown error"
        return CheckResult(
            passed=False,
            failed_reasons=[f"工具执行失败：{error}"],
            suggested_fix=["检查工具名称或工具实现"],
        )

    def _should_check_summary(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "summarize"
            and result.tool_name in {"text_tool", "report_tool"}
        )

    def _should_check_table_report(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "data_analysis"
            and result.tool_name == "report_tool"
        )

    def _should_check_research_report(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "research"
            and result.tool_name == "report_tool"
        )

    def _check_research_report(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        failed_reasons = []
        suggested_fix = []

        for section in RESEARCH_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section, RESEARCH_REQUIRED_SECTIONS)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")

        source_results = result.result.get("source_search_results") or []
        if source_results:
            for item in source_results:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if url and url not in report_text:
                    failed_reasons.append(f"来源缺少 URL：{url}")
                    suggested_fix.append(f"在来源小节补充 URL：{url}")
        elif "未找到可用来源" not in report_text:
            failed_reasons.append("无搜索结果时必须写明：未找到可用来源")
            suggested_fix.append("在结论或来源小节写明：未找到可用来源")

        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _check_summary(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        failed_reasons = []
        suggested_fix = []

        for section in SUMMARY_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")

        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _check_table_report(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        source_stats = result.result.get("source_table_stats") or {}
        failed_reasons = []
        suggested_fix = []
        headings = TABLE_REQUIRED_SECTIONS + ["分类汇总", "业务解释", "后续建议"]

        for section in TABLE_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section, headings)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")

        field_section = self._section_content(report_text, "字段说明", headings) or ""
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

    def check_table_numbers(self, report_text: str, table_stats: dict) -> CheckResult:
        mapping = [
            ("row_count", "行数"),
            ("column_count", "列数"),
            ("missing_count", "缺失值数量"),
            ("anomaly_count", "异常值数量"),
        ]
        failed_reasons = []
        suggested_fix = []

        for key, label in mapping:
            expected = table_stats.get(key)
            actual = self._extract_labeled_number(report_text, label)
            if actual is None:
                failed_reasons.append(f"报告缺少数字：{label}")
                suggested_fix.append(f"补充{label}")
            elif actual != expected:
                failed_reasons.append(f"{label}不一致：报告={actual}，工具={expected}")
                suggested_fix.append(f"把{label}改为 {expected}")

        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _extract_labeled_number(self, text: str, label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\s*[：:]?\s*(\d+)", text)
        if not match:
            return None
        return int(match.group(1))
