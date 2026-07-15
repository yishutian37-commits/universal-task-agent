from __future__ import annotations

import re
from typing import Any

from core.intent_rules import current_user_input, looks_like_langchain_tool_task
from core.state import Task
from llm.llm_client import LLMClient


ALLOWED_TASK_TYPES = {
    "summarize",
    "data_analysis",
    "research",
    "code_reading",
    "geo_analysis",
    "history_query",
    "langchain_tool",
    "complex_task",
    "unknown",
}


class TaskParser:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client if llm_client is not None else LLMClient.from_config()

    def parse(self, task_id: str, user_input: str) -> Task:
        current_input = self._current_user_input(user_input)
        if self._looks_like_workspace_summary(current_input):
            return self._workspace_summary_task(task_id, current_input)
        try:
            payload = self.llm_client.chat_json(
                self._system_prompt(),
                self._user_prompt(user_input),
                schema=None,
            )
        except Exception:
            return self._ensure_required_info(
                self._fallback_task(task_id, current_input),
                current_input,
            )

        if not isinstance(payload, dict):
            return self._ensure_required_info(
                self._fallback_task(task_id, current_input),
                current_input,
            )

        if self._looks_like_history_query(current_input):
            return self._history_query_task(task_id, current_input)
        if self._looks_like_langchain_tool_task(current_input):
            return self._langchain_tool_task(task_id, current_input)

        task_type = self._normalize_task_type(payload.get("task_type"))
        if self._looks_like_complex_task(current_input) and task_type in {"summarize", "code_reading", "unknown"}:
            return self._complex_task(task_id, current_input)

        return self._ensure_required_info(Task(
            task_id=task_id,
            user_input=current_input,
            task_type=task_type,
            intent=self._string_or_default(payload.get("intent"), task_type),
            input_type=self._string_or_default(payload.get("input_type"), "unknown"),
            expected_output=self._string_or_default(payload.get("expected_output"), "unknown"),
            constraints=self._list_or_empty(payload.get("constraints")),
            missing_info=self._list_or_empty(payload.get("missing_info")),
        ), current_input)

    @staticmethod
    def _ensure_required_info(task: Task, user_input: str) -> Task:
        normalized = "".join(str(user_input or "").lower().split())
        normalized = re.sub(r"[。.!！?？]+$", "", normalized)
        summary_without_source = normalized in {
            "总结",
            "总结一下",
            "帮我总结",
            "帮我总结一下",
            "请总结",
            "请总结一下",
            "请帮我总结",
            "请帮我总结一下",
            "摘要",
            "生成摘要",
        }
        if task.task_type == "summarize" and summary_without_source and not task.missing_info:
            task.missing_info = ["需要总结的文本或文件"]
        return task

    @staticmethod
    def _current_user_input(user_input: str) -> str:
        return current_user_input(user_input)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的 Task Parser。只返回 JSON，不要输出解释。"
            "task_type 只能是 summarize、data_analysis、research、code_reading、geo_analysis、history_query、langchain_tool、complex_task、unknown。"
            "missing_info 只填写不补充就无法安全开始任务的必要信息；"
            "可选格式、篇幅、语气或可使用默认值的信息不算缺失。"
        )

    @staticmethod
    def _user_prompt(user_input: str) -> str:
        return (
            "请解析这个用户任务，并返回 JSON，字段包括："
            "task_type、intent、input_type、expected_output、constraints、missing_info。\n"
            f"用户任务：{user_input}"
        )

    @staticmethod
    def _normalize_task_type(value: Any) -> str:
        if isinstance(value, str) and value in ALLOWED_TASK_TYPES:
            return value
        return "unknown"

    @staticmethod
    def _string_or_default(value: Any, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return default

    @staticmethod
    def _list_or_empty(value: Any) -> list:
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _fallback_task(task_id: str, user_input: str) -> Task:
        guessed_type = TaskParser._guess_task_type(user_input)
        if guessed_type == "data_analysis":
            return Task(
                task_id=task_id,
                user_input=user_input,
                task_type="data_analysis",
                intent="analyze_table",
                input_type="file",
                expected_output="analysis_report",
                constraints=[],
                missing_info=[],
            )
        if guessed_type == "research":
            return Task(
                task_id=task_id,
                user_input=user_input,
                task_type="research",
                intent="research_topic",
                input_type="text",
                expected_output="research_report",
                constraints=[],
                missing_info=[],
            )
        if guessed_type == "summarize":
            return Task(
                task_id=task_id,
                user_input=user_input,
                task_type="summarize",
                intent="summarize_article",
                input_type="text",
                expected_output="summary_report",
                constraints=[],
                missing_info=[],
            )
        if guessed_type == "code_reading":
            return Task(
                task_id=task_id,
                user_input=user_input,
                task_type="code_reading",
                intent="read_task_flow",
                input_type="repository",
                expected_output="code_reading_report",
                constraints=[],
                missing_info=[],
            )
        if guessed_type == "geo_analysis":
            return Task(
                task_id=task_id,
                user_input=user_input,
                task_type="geo_analysis",
                intent="geo_analysis",
                input_type="text",
                expected_output="geo_report",
                constraints=[],
                missing_info=[],
            )
        if guessed_type == "history_query":
            return TaskParser._history_query_task(task_id, user_input)
        if guessed_type == "langchain_tool":
            return TaskParser._langchain_tool_task(task_id, user_input)
        if guessed_type == "complex_task":
            return TaskParser._complex_task(task_id, user_input)
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="unknown",
            intent="parse_failed",
            input_type="unknown",
            expected_output="unknown",
            constraints=[],
            missing_info=["task_type"],
        )

    @staticmethod
    def _guess_task_type(user_input: str) -> str:
        text = user_input.lower()
        if TaskParser._looks_like_history_query(user_input):
            return "history_query"
        if TaskParser._looks_like_langchain_tool_task(user_input):
            return "langchain_tool"
        if any(marker in text for marker in ["geo", "生成式引擎优化"]):
            return "geo_analysis"
        if any(marker in user_input for marker in ["AI可见性", "AI 可见性", "问题矩阵", "内容Brief", "内容 Brief", "平台合规"]):
            return "geo_analysis"
        if any(marker in text for marker in [".csv", ".xlsx", "csv", "excel", "xlsx", "表格"]):
            return "data_analysis"
        if any(
            marker in user_input
            for marker in [
                "调研",
                "搜索",
                "查找",
                "资料",
                "来源",
                "研究",
                "竞品",
                "趋势",
                "天气",
                "气温",
                "温度",
                "降雨",
                "降水",
                "湿度",
                "风力",
            ]
        ):
            return "research"
        if TaskParser._looks_like_complex_task(user_input):
            return "complex_task"
        if any(
            marker in user_input
            for marker in ["代码", "源码", "调用链", "任务链路", "阅读项目", "项目结构", "从输入到输出"]
        ):
            return "code_reading"
        if "总结" in user_input or "摘要" in user_input:
            return "summarize"
        return "unknown"

    @staticmethod
    def _looks_like_history_query(user_input: str) -> bool:
        return any(
            marker in user_input
            for marker in [
                "之前让你",
                "之前给你",
                "之前叫你",
                "之前让你做",
                "以前让你",
                "历史任务",
                "任务历史",
                "任务记录",
                "做过什么任务",
                "进行过什么任务",
                "分配过什么任务",
                "列出之前",
                "列出来之前",
            ]
        )

    @staticmethod
    def _history_query_task(task_id: str, user_input: str) -> Task:
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="history_query",
            intent="list_previous_tasks",
            input_type="memory",
            expected_output="history_task_list",
            constraints=[],
            missing_info=[],
        )

    @staticmethod
    def _looks_like_langchain_tool_task(user_input: str) -> bool:
        return looks_like_langchain_tool_task(user_input)

    @staticmethod
    def _looks_like_workspace_summary(user_input: str) -> bool:
        normalized = "".join(str(user_input or "").lower().split())
        return (
            "总结" in normalized
            and any(marker in normalized for marker in ("读取", "查看", "分析"))
            and any(
                marker in normalized
                for marker in ("工作区", "工作文件夹", "工作目录", "当前目录", "这个文件夹", "该文件夹")
            )
        )

    @staticmethod
    def _workspace_summary_task(task_id: str, user_input: str) -> Task:
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="summarize",
            intent="summarize_workspace",
            input_type="directory",
            expected_output="summary_report",
            constraints=["只读工作区，不修改文件"],
            missing_info=[],
        )

    @staticmethod
    def _langchain_tool_task(task_id: str, user_input: str) -> Task:
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="langchain_tool",
            intent="invoke_langchain_tool",
            input_type="text",
            expected_output="tool_result",
            constraints=[],
            missing_info=[],
        )

    @staticmethod
    def _looks_like_complex_task(user_input: str) -> bool:
        text = user_input.lower()
        if any(
            marker in user_input
            for marker in [
                "复杂任务",
                "分步骤",
                "拆分任务",
                "拆解任务",
                "任务拆解",
                "依次执行",
                "分步执行",
                "一步一步",
                "按步骤",
                "列出步骤",
            ]
        ):
            return True
        if any(marker in text for marker in ["[1]", "[2]", "[3]"]):
            return True

        task_section = TaskParser._task_list_section(user_input)
        if task_section != user_input and TaskParser._numbered_marker_count(task_section) >= 2:
            return True

        return (
            TaskParser._numbered_marker_count(user_input) >= 3
            and TaskParser._task_action_count(user_input) >= 2
        )

    @staticmethod
    def _task_list_section(user_input: str) -> str:
        cues = [
            "你可以让 Agent 做这几个任务",
            "让 Agent 做这几个任务",
            "做这几个任务",
            "执行这几个任务",
            "完成这几个任务",
            "任务清单",
            "任务列表",
        ]
        for cue in cues:
            index = user_input.find(cue)
            if index >= 0:
                return user_input[index + len(cue) :]
        return user_input

    @staticmethod
    def _numbered_marker_count(text: str) -> int:
        pattern = re.compile(r"(?:\[\d+\]|（\d+）|\(\d+\)|(?<![\d.])\d{1,2}[.、](?!\d))")
        return len(pattern.findall(text))

    @staticmethod
    def _task_action_count(user_input: str) -> int:
        return sum(
            1
            for marker in [
                "总结",
                "提炼",
                "提取",
                "找出",
                "判断",
                "压缩",
                "改写",
                "分析",
                "列出",
                "生成",
            ]
            if marker in user_input
        )

    @staticmethod
    def _complex_task(task_id: str, user_input: str) -> Task:
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type="complex_task",
            intent="execute_complex_task",
            input_type="text",
            expected_output="step_checklist",
            constraints=[],
            missing_info=[],
        )
