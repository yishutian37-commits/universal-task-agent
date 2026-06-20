import re

from core.state import AgentState, CheckResult, PlanStep, ToolResult


SUMMARY_REQUIRED_SECTIONS = ["摘要", "核心观点", "风险点"]


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
            and result.tool_name == "report_tool"
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

    def _section_content(self, report_text: str, section: str) -> str | None:
        headings = "|".join(re.escape(item) for item in SUMMARY_REQUIRED_SECTIONS + ["关键事实", "待办事项"])
        pattern = re.compile(
            rf"(?:^|\n)[ \t]*(?:#+[ \t]*)?{re.escape(section)}[ \t]*[：:]?[ \t]*\n?"
            rf"(.*?)(?=\n[ \t]*(?:#+[ \t]*)?(?:{headings})[ \t]*[：:]?[ \t]*\n?|\Z)",
            re.DOTALL,
        )
        match = pattern.search(report_text)
        if not match:
            return None
        return match.group(1).strip()
