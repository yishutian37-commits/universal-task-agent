import re
import json
from pathlib import Path

from core.state import AgentState, CheckResult, CriterionResult, PlanStep, ToolResult


SUMMARY_REQUIRED_SECTIONS = ["摘要", "核心观点", "风险点"]
TABLE_REQUIRED_SECTIONS = ["字段说明", "基础统计", "异常数据"]
RESEARCH_REQUIRED_SECTIONS = ["结论", "关键发现", "来源", "注意事项"]
CODE_REQUIRED_SECTIONS = ["任务链路", "关键文件", "模块职责", "调用顺序", "状态与记忆", "桌面端入口", "风险点", "下一步建议"]
CODE_REQUIRED_FILES = ["main.py", "core/loop.py", "core/router.py", "core/verifier.py"]
GEO_REQUIRED_SECTIONS = ["事实输入", "事实缺口", "问题矩阵", "内容Brief", "平台合规", "规则来源", "下一步建议"]
DETERMINISTIC_TOOL_NAMES = {
    "langchain_directory_create_tool",
    "langchain_file_write_tool",
    "langchain_file_delete_tool",
    "langchain_shell_tool",
    "langchain_python_repl_tool",
}


class Verifier:
    def check_criteria(
        self,
        state: AgentState,
        step: PlanStep,
        result: ToolResult,
        *,
        plan_id: str,
        attempt: int = 1,
    ) -> list[CriterionResult]:
        return [
            self._check_criterion(
                state,
                step,
                result,
                criterion,
                plan_id=plan_id,
                attempt=attempt,
            )
            for criterion in step.success_criteria
        ]

    def _check_criterion(
        self,
        state: AgentState,
        step: PlanStep,
        result: ToolResult,
        criterion: str,
        *,
        plan_id: str,
        attempt: int,
    ) -> CriterionResult:
        base = {
            "task_id": state.task_id,
            "plan_id": plan_id,
            "step_id": step.step_id,
            "criterion": criterion,
            "attempt": attempt,
        }
        if not result.success:
            return CriterionResult(
                **base,
                status="failed",
                passed=False,
                source="deterministic",
                evidence=[{"kind": "tool_error", "error": result.error or "unknown error"}],
                failure_reason="工具执行失败，无法满足成功标准",
            )

        if result.tool_name in DETERMINISTIC_TOOL_NAMES:
            check = self.check(state, step, result)
            evidence = self._deterministic_evidence(state, step, result)
            if check.passed:
                return CriterionResult(
                    **base,
                    status="passed",
                    passed=True,
                    source="deterministic",
                    evidence=evidence,
                )
            return CriterionResult(
                **base,
                status="failed",
                passed=False,
                source="deterministic",
                evidence=evidence,
                failure_reason="；".join(check.failed_reasons) or "缺少确定性执行证据",
            )

        text_key, text = self._criterion_text(result)
        evidence = (
            [{"kind": "tool_result", "key": text_key, "preview": text[:500]}]
            if text
            else [{"kind": "tool_result", "keys": sorted(result.result)}]
        )
        if (
            state.task_type == "summarize"
            and result.tool_name in {"text_tool", "report_tool"}
            and any(marker in criterion for marker in ("结构化摘要", "结构化总结"))
        ):
            summary_check = self._check_summary(result)
            if summary_check.passed:
                return CriterionResult(
                    **base,
                    status="passed",
                    passed=True,
                    source="deterministic",
                    evidence=evidence,
                )
            return CriterionResult(
                **base,
                status="failed",
                passed=False,
                source="deterministic",
                evidence=evidence,
                failure_reason="；".join(summary_check.failed_reasons),
            )

        if "包含" in criterion:
            expected = self._contained_terms(criterion)
            missing = [term for term in expected if term not in text]
            if expected and not missing:
                return CriterionResult(
                    **base,
                    status="passed",
                    passed=True,
                    source="tool_result",
                    evidence=evidence,
                )
            return CriterionResult(
                **base,
                status="failed",
                passed=False,
                source="tool_result",
                evidence=evidence,
                failure_reason=(
                    "工具输出缺少：" + "、".join(missing)
                    if missing
                    else "成功标准未声明可核对的包含项"
                ),
            )

        if criterion in text or (
            any(marker in criterion for marker in ("读取到", "已获得", "已生成", "已输出", "已经创建", "已经写入", "完成"))
            and bool(text or result.result)
        ):
            return CriterionResult(
                **base,
                status="passed",
                passed=True,
                source="tool_result",
                evidence=evidence,
            )

        return CriterionResult(
            **base,
            status="indeterminate",
            passed=False,
            source="unverified",
            evidence=evidence,
            failure_reason="现有工具输出和证据无法判定该成功标准",
        )

    @staticmethod
    def _criterion_text(result: ToolResult) -> tuple[str, str]:
        for key in ("message", "report_markdown", "summary_markdown", "content", "output"):
            value = result.result.get(key)
            if isinstance(value, str) and value.strip():
                return key, value.strip()
            if isinstance(value, (dict, list)) and value:
                return key, json.dumps(value, ensure_ascii=False)
        return "", ""

    @staticmethod
    def _contained_terms(criterion: str) -> list[str]:
        expected = criterion.split("包含", 1)[1]
        return [
            item.strip(" ：:。；;，,、")
            for item in re.split(r"(?:、|，|,|和|与|及)", expected)
            if item.strip(" ：:。；;，,、")
        ]

    @staticmethod
    def _deterministic_evidence(
        state: AgentState,
        step: PlanStep,
        result: ToolResult,
    ) -> list[dict]:
        evidence = []
        for key in ("path", "trash_path", "cwd", "command", "returncode", "output"):
            value = result.result.get(key)
            if value not in (None, ""):
                evidence.append({"kind": "tool_result", "key": key, key: value})
        for bucket in ("files", "changes", "artifacts"):
            for item in state.evidence.get(bucket, []):
                if item.get("step_id") == step.step_id:
                    evidence.append({"kind": bucket, **item})
        return evidence

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

        if result.tool_name == "langchain_directory_create_tool":
            return self._check_directory_creation(result)

        if result.tool_name == "langchain_file_write_tool":
            return self._check_file_write(result)

        if result.tool_name == "langchain_file_delete_tool":
            return self._check_file_delete(result)

        if self._should_check_summary(state, result):
            return self._check_summary(result)

        if self._should_check_research_report(state, result):
            return self._check_research_report(result)

        if self._should_check_table_report(state, result):
            return self._check_table_report(result)

        if self._should_check_code_report(state, result):
            return self._check_code_report(result)

        if self._should_check_geo_report(state, result):
            return self._check_geo_report(result)

        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    def _check_directory_creation(self, result: ToolResult) -> CheckResult:
        path = self._result_path(result, "path")
        if path is None or not path.is_dir():
            return CheckResult(
                passed=False,
                failed_reasons=["目录创建结果不存在"],
                suggested_fix=["检查目标路径并重新创建目录"],
            )
        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    def _check_file_write(self, result: ToolResult) -> CheckResult:
        path = self._result_path(result, "path")
        if path is None or not path.is_file():
            return CheckResult(
                passed=False,
                failed_reasons=["写入后的文件不存在"],
                suggested_fix=["检查目标路径并重新写入文件"],
            )

        expected_bytes = int(result.result.get("bytes_written") or 0)
        mode = str(result.result.get("mode") or "create")
        actual_bytes = path.stat().st_size
        size_matches = actual_bytes >= expected_bytes if mode == "append" else actual_bytes == expected_bytes
        if expected_bytes and not size_matches:
            return CheckResult(
                passed=False,
                failed_reasons=["文件字节数与工具结果不一致"],
                suggested_fix=["重新读取目标文件并确认写入内容"],
            )
        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    def _check_file_delete(self, result: ToolResult) -> CheckResult:
        original = self._result_path(result, "path")
        trash = self._result_path(result, "trash_path")
        if original is None:
            return CheckResult(False, ["删除结果缺少原路径"], ["补充被删除路径"])
        if original.exists():
            return CheckResult(False, ["删除后原路径仍然存在"], ["重新执行移动到回收站操作"])
        if trash is None or not trash.exists():
            return CheckResult(False, ["UTA 回收路径不存在"], ["确认文件已安全移动到 UTA 回收站"])
        return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

    @staticmethod
    def _result_path(result: ToolResult, key: str) -> Path | None:
        value = result.result.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        return Path(value).expanduser().resolve()

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

    def _should_check_code_report(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "code_reading"
            and result.tool_name == "report_tool"
        )

    def _should_check_geo_report(self, state: AgentState | None, result: ToolResult) -> bool:
        return (
            state is not None
            and state.task_type == "geo_analysis"
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

    def _check_code_report(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        source_analysis = result.result.get("source_code_analysis") or {}
        source_files = source_analysis.get("files") if isinstance(source_analysis, dict) else []
        if not isinstance(source_files, list):
            source_files = []

        failed_reasons = []
        suggested_fix = []

        for section in CODE_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section, CODE_REQUIRED_SECTIONS)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")

        scanned_paths = {
            str(item.get("path") or "")
            for item in source_files
            if isinstance(item, dict)
        }
        key_files_section = self._section_content(report_text, "关键文件", CODE_REQUIRED_SECTIONS) or ""

        for path in CODE_REQUIRED_FILES:
            if path not in scanned_paths:
                failed_reasons.append(f"扫描结果缺少关键文件：{path}")
                suggested_fix.append(f"补充扫描关键文件：{path}")
            if path not in key_files_section:
                failed_reasons.append(f"关键文件小节缺少文件：{path}")
                suggested_fix.append(f"在关键文件小节补充：{path}")

        return CheckResult(
            passed=not failed_reasons,
            failed_reasons=failed_reasons,
            suggested_fix=suggested_fix,
        )

    def _check_geo_report(self, result: ToolResult) -> CheckResult:
        report_text = str(result.result.get("message") or result.result.get("report_markdown") or "")
        source_analysis = result.result.get("source_geo_analysis") or {}
        question_matrix = source_analysis.get("question_matrix") if isinstance(source_analysis, dict) else []
        if not isinstance(question_matrix, list):
            question_matrix = []

        failed_reasons = []
        suggested_fix = []

        for section in GEO_REQUIRED_SECTIONS:
            content = self._section_content(report_text, section, GEO_REQUIRED_SECTIONS)
            if content is None:
                failed_reasons.append(f"缺少必要小节：{section}")
                suggested_fix.append(f"补齐{section}小节")
            elif not content.strip():
                failed_reasons.append(f"小节内容为空：{section}")
                suggested_fix.append(f"补充{section}小节内容")

        if not question_matrix:
            failed_reasons.append("GEO 分析缺少问题矩阵")
            suggested_fix.append("补充 GEO 问题矩阵")

        matrix_section = self._section_content(report_text, "问题矩阵", GEO_REQUIRED_SECTIONS) or ""
        for item in question_matrix:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if question and question not in matrix_section:
                failed_reasons.append(f"问题矩阵小节缺少问题：{question}")
                suggested_fix.append(f"在问题矩阵小节补充：{question}")

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
