from core.state import AgentState, CheckResult, Feedback, PlanStep, ToolResult


class Reflection:
    def analyze(
        self,
        state: AgentState,
        step: PlanStep,
        result: ToolResult,
        check: CheckResult,
    ) -> Feedback:
        del state, step
        root_cause = "；".join(check.failed_reasons) or result.error or "未知失败"
        repair_strategy = "；".join(check.suggested_fix) or "重新执行当前步骤"
        return Feedback(
            failure_type=self._failure_type(result, check),
            root_cause=root_cause,
            repair_strategy=repair_strategy,
            need_replan=False,
            need_user_input=False,
        )

    def _failure_type(self, result: ToolResult, check: CheckResult) -> str:
        if not result.success:
            return "tool_error"

        joined = "；".join(check.failed_reasons)
        if "缺少必要小节" in joined or "小节内容为空" in joined:
            return "incomplete_output"
        if "不一致" in joined:
            return "violated_constraint"
        return "format_error"
