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
        need_user_input = self._needs_user_input(root_cause, repair_strategy)
        return Feedback(
            failure_type=self._failure_type(result, check),
            root_cause=root_cause,
            repair_strategy=repair_strategy,
            need_replan=False,
            need_user_input=need_user_input,
        )

    @staticmethod
    def _needs_user_input(root_cause: str, repair_strategy: str) -> bool:
        text = f"{root_cause}\n{repair_strategy}".lower()
        return any(
            marker in text
            for marker in (
                "请提供",
                "请补充",
                "未提供",
                "缺少输入",
                "路径不存在",
                "缺少文件路径",
                "缺少目录路径",
                "缺少删除路径",
                "缺少 shell 命令",
                "缺少 python 代码",
                "no such file",
                "missing input",
            )
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
