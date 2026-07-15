import json
from typing import Any

from core.intent_rules import current_user_input, langchain_tool_name
from core.state import Action, AgentState, PlanStep
from core.tool_catalog import build_tool_catalog, get_action_contract, validate_action_params


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

    def __init__(
        self,
        llm_client=None,
        tool_registry=None,
        tool_catalog: list[dict[str, Any]] | None = None,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry if tool_registry is not None else {}
        self.tool_catalog = (
            list(tool_catalog)
            if tool_catalog is not None
            else build_tool_catalog(self.tool_registry)
        )
        self.catalog_by_name = {
            str(item.get("name")): item
            for item in self.tool_catalog
            if isinstance(item, dict) and item.get("name")
        }

    def choose_tool(self, state: AgentState, step: PlanStep) -> Action:
        goal_lower = step.goal.lower()
        if state.task_type == "langchain_tool":
            return self._langchain_action(state, step)
        if self._looks_like_unsupported_local_computer_task(state, step):
            return self._unsupported_action(state, step, "当前版本不支持操作本地电脑、鼠标键盘、桌面文件或其他本地应用")
        hinted_action = self._hinted_action(state, step)
        if hinted_action is not None:
            return hinted_action
        model_action = self._model_action(state, step)
        if model_action is not None:
            return model_action
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

    def _hinted_action(self, state: AgentState, step: PlanStep) -> Action | None:
        if not step.tool_hint or step.tool_hint not in self.tool_registry:
            return None
        catalog_item = self.catalog_by_name.get(step.tool_hint, {})
        action_name = step.action_hint or str(catalog_item.get("default_action") or "run")
        action_contract = get_action_contract(catalog_item, action_name)
        if action_contract is None or not validate_action_params(
            action_contract.get("parameter_schema"),
            step.inputs,
        ):
            return None
        return self._action(
            state,
            step,
            step.tool_hint,
            action_name,
            f"计划步骤指定工具：{step.tool_hint}",
            extra_params=step.inputs,
        )

    def _model_action(self, state: AgentState, step: PlanStep) -> Action | None:
        chat_json = getattr(self.llm_client, "chat_json", None)
        if not callable(chat_json) or not self.tool_registry:
            return None
        try:
            payload = chat_json(
                self._system_prompt(),
                self._user_prompt(state, step),
                schema=self._response_schema(),
            )
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        tool_name = payload.get("tool_name")
        action_name = payload.get("action_name")
        params = payload.get("params") or {}
        if (
            not isinstance(tool_name, str)
            or tool_name not in self.tool_registry
            or not isinstance(action_name, str)
            or not action_name.strip()
            or not isinstance(params, dict)
        ):
            return None
        action_contract = get_action_contract(self.catalog_by_name.get(tool_name), action_name.strip())
        if action_contract is None or not validate_action_params(
            action_contract.get("parameter_schema"),
            params,
        ):
            return None
        reason = payload.get("reason")
        return self._action(
            state,
            step,
            tool_name,
            action_name.strip(),
            reason.strip() if isinstance(reason, str) and reason.strip() else f"模型选择：{tool_name}",
            extra_params=params,
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的工具 Router。只返回 JSON，不要输出解释。"
            "tool_name 只能来自给定工具目录，不得虚构工具。"
        )

    def _user_prompt(self, state: AgentState, step: PlanStep) -> str:
        previous_result = state.results[-1].result if state.results else None
        return (
            "请为当前步骤选择一个工具。返回 tool_name、action_name、params、reason。\n"
            f"任务：{state.execution_input or state.user_input}\n"
            f"当前步骤：{step.goal}\n"
            f"前置结果：{json.dumps(previous_result, ensure_ascii=False)}\n"
            f"工具目录：{json.dumps(self.tool_catalog, ensure_ascii=False)}"
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["tool_name", "action_name", "params"],
            "properties": {
                "tool_name": {"type": "string"},
                "action_name": {"type": "string"},
                "params": {"type": "object"},
                "reason": {"type": "string"},
            },
        }

    def _looks_like_unsupported_local_computer_task(self, state: AgentState, step: PlanStep) -> bool:
        text = f"{state.user_input}\n{state.execution_input or ''}\n{step.goal}"
        return any(keyword in text for keyword in self.LOCAL_COMPUTER_ACTION_KEYWORDS)

    def _langchain_action(self, state: AgentState, step: PlanStep) -> Action:
        text = current_user_input(state.execution_input or state.user_input)
        tool_name = langchain_tool_name(text)
        if tool_name is None:
            return self._unsupported_action(state, step, "没有匹配到安全 LangChain 工具")
        catalog_item = self.catalog_by_name.get(tool_name, {})
        action_name = str(catalog_item.get("default_action") or "invoke")
        action = self._action(
            state,
            step,
            tool_name,
            action_name,
            f"LangChain 工具路由：{tool_name}",
        )
        if tool_name.startswith("langchain_"):
            action.params["tool_input"] = {"query": text}
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
        extra_params: dict[str, Any] | None = None,
    ) -> Action:
        if self.tool_registry:
            if tool_name not in self.tool_registry:
                return self._unsupported_action(state, step, f"工具未注册：{tool_name}")
            action_contract = get_action_contract(self.catalog_by_name.get(tool_name), action_name)
            if action_contract is None or not validate_action_params(
                action_contract.get("parameter_schema"),
                extra_params or {},
            ):
                return self._unsupported_action(
                    state,
                    step,
                    f"工具 action 或参数不符合契约：{tool_name}.{action_name}",
                )
        previous_result = state.results[-1].result if state.results else None
        params = dict(extra_params or {})
        params.update(
            {
                "user_input": state.execution_input or state.user_input,
                "goal": step.goal,
                "previous_result": previous_result,
            }
        )
        return Action(
            action_id=f"action_{state.task_id}_{step.step_id}",
            step_id=step.step_id,
            tool_name=tool_name,
            action_name=action_name,
            params=params,
            reason=reason,
        )
