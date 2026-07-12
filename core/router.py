from core.intent_rules import langchain_tool_name
from core.state import Action, AgentState, PlanStep


class Router:
    LOCAL_COMPUTER_ACTION_KEYWORDS = (
        "操作本地电脑",
        "控制本地电脑",
        "控制我的电脑",
        "操作我的电脑",
        "控制鼠标",
        "移动鼠标",
        "点击鼠标",
        "控制键盘",
        "按键盘",
        "打开本地应用",
        "控制本地应用",
        "打开微信",
        "操作微信",
        "打开浏览器",
        "整理桌面",
        "桌面文件",
        "删除本地文件",
        "移动本地文件",
    )
    COMPLEX_TEXT_KEYWORDS = (
        "总结",
        "分析",
        "提炼",
        "归纳",
        "改写",
        "压缩",
        "计划",
        "建议",
        "一句话",
        "核心观点",
        "关键结论",
        "逻辑结构",
        "作者",
        "小白",
        "朋友圈",
        "知乎",
    )

    RULES = [
        (("历史任务", "任务历史", "任务记录", "读取历史", "之前任务"), "history_tool", "list"),
        (("GEO 规则包", "生成式引擎优化", "AI可见性", "AI 可见性", "问题矩阵", "内容Brief", "内容 Brief", "平台合规"), "geo_tool", "analyze"),
        (("LangChain 工具", "langchain 工具", "LangChain 回显", "langchain 回显"), "langchain_echo_tool", "invoke"),
        (("读取", "文件", "txt", "md", "csv", "excel", "表格文件"), "file_tool", "read"),
        (("文本", "摘要", "提取", "核心信息", "核心观点"), "text_tool", "process"),
        (("报告", "Markdown", "输出", "调研报告"), "report_tool", "generate"),
        (("代码", "源码", "扫描", "链路", "函数", "类名", "项目结构"), "code_tool", "scan"),
        (
            ("搜索", "调研", "查找", "资料", "来源", "研究", "竞品", "趋势", "天气", "气温", "温度"),
            "search_tool",
            "search",
        ),
        (("表格", "字段", "行数", "列数", "缺失值", "异常值"), "table_tool", "analyze"),
    ]

    def choose_tool(self, state: AgentState, step: PlanStep) -> Action:
        goal_lower = step.goal.lower()
        if state.task_type == "langchain_tool":
            return self._langchain_action(state, step)
        if self._looks_like_unsupported_local_computer_task(state, step):
            return self._unsupported_action(state, step, "当前版本不支持操作本地电脑、鼠标键盘、桌面文件或其他本地应用")
        if state.task_type == "complex_task" and any(keyword in step.goal for keyword in self.COMPLEX_TEXT_KEYWORDS):
            return self._action(
                state,
                step,
                "text_tool",
                "process",
                f"复杂任务文本步骤：{step.goal}",
            )
        for keywords, tool_name, action_name in self.RULES:
            if any(keyword.lower() in goal_lower for keyword in keywords):
                return self._action(
                    state,
                    step,
                    tool_name,
                    action_name,
                    f"规则命中：{step.goal}",
                )
        return self._unsupported_action(state, step, "当前任务不支持：没有匹配到可用工具，已停止执行，避免伪完成")

    def _looks_like_unsupported_local_computer_task(self, state: AgentState, step: PlanStep) -> bool:
        text = f"{state.user_input}\n{state.execution_input or ''}\n{step.goal}"
        return any(keyword in text for keyword in self.LOCAL_COMPUTER_ACTION_KEYWORDS)

    def _langchain_action(self, state: AgentState, step: PlanStep) -> Action:
        text = state.user_input
        tool_name = langchain_tool_name(text)
        if tool_name is None:
            return self._unsupported_action(state, step, "没有匹配到安全 LangChain 工具")
        action = self._action(
            state,
            step,
            tool_name,
            "invoke",
            f"LangChain 工具路由：{tool_name}",
        )
        if tool_name in {
            "langchain_directory_create_tool",
            "langchain_file_delete_tool",
            "langchain_file_write_tool",
            "langchain_shell_tool",
            "langchain_python_repl_tool",
        }:
            action.params["tool_input"] = {"query": state.user_input}
        return action

    def _unsupported_action(self, state: AgentState, step: PlanStep, reason: str) -> Action:
        return Action(
            action_id=f"action_{state.task_id}_{step.step_id}",
            step_id=step.step_id,
            tool_name="unsupported_task",
            action_name="unsupported",
            params={
                "user_input": state.execution_input or state.user_input,
                "goal": step.goal,
                "previous_result": state.results[-1].result if state.results else None,
                "unsupported_reason": reason,
            },
            reason=f"不支持：{reason}",
        )

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
                "user_input": state.execution_input or state.user_input,
                "goal": step.goal,
                "previous_result": previous_result,
            },
            reason=reason,
        )
