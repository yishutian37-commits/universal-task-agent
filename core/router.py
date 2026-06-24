from core.state import Action, AgentState, PlanStep


class Router:
    RULES = [
        (("读取", "文件", "txt", "md", "csv", "excel", "表格文件"), "file_tool", "read"),
        (("文本", "摘要", "提取", "核心信息", "核心观点", "风险"), "text_tool", "process"),
        (("报告", "Markdown", "输出", "调研报告"), "report_tool", "generate"),
        (("代码", "源码", "扫描", "链路", "函数", "类", "项目结构"), "code_tool", "scan"),
        (
            ("搜索", "调研", "查找", "资料", "来源", "研究", "竞品", "趋势", "天气", "气温", "温度"),
            "search_tool",
            "search",
        ),
        (("表格", "字段", "行数", "列数", "缺失值", "异常值"), "table_tool", "analyze"),
    ]

    def choose_tool(self, state: AgentState, step: PlanStep) -> Action:
        goal_lower = step.goal.lower()
        for keywords, tool_name, action_name in self.RULES:
            if any(keyword.lower() in goal_lower for keyword in keywords):
                return self._action(
                    state,
                    step,
                    tool_name,
                    action_name,
                    f"规则命中：{step.goal}",
                )
        return self._action(state, step, "mock_tool", "run", "规则未命中，使用 mock_tool 兜底")

    def _action(
        self,
        state: AgentState,
        step: PlanStep,
        tool_name: str,
        action_name: str,
        reason: str,
    ) -> Action:
        previous_result = state.results[-1].result if state.results else None
        return Action(
            action_id=f"action_{state.task_id}_{step.step_id}",
            step_id=step.step_id,
            tool_name=tool_name,
            action_name=action_name,
            params={
                "user_input": state.user_input,
                "goal": step.goal,
                "previous_result": previous_result,
            },
            reason=reason,
        )
