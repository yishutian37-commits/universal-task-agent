from __future__ import annotations

from typing import Any

from core.state import Task
from llm.llm_client import LLMClient


ALLOWED_TASK_TYPES = {"summarize", "data_analysis", "unknown"}


class TaskParser:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client if llm_client is not None else LLMClient.from_config()

    def parse(self, task_id: str, user_input: str) -> Task:
        try:
            payload = self.llm_client.chat_json(
                self._system_prompt(),
                self._user_prompt(user_input),
                schema=None,
            )
        except Exception:
            return self._fallback_task(task_id, user_input)

        if not isinstance(payload, dict):
            return self._fallback_task(task_id, user_input)

        task_type = self._normalize_task_type(payload.get("task_type"))
        return Task(
            task_id=task_id,
            user_input=user_input,
            task_type=task_type,
            intent=self._string_or_default(payload.get("intent"), task_type),
            input_type=self._string_or_default(payload.get("input_type"), "unknown"),
            expected_output=self._string_or_default(payload.get("expected_output"), "unknown"),
            constraints=self._list_or_empty(payload.get("constraints")),
            missing_info=self._list_or_empty(payload.get("missing_info")),
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的 Task Parser。只返回 JSON，不要输出解释。"
            "task_type 只能是 summarize、data_analysis、unknown。"
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
        if any(marker in text for marker in [".csv", ".xlsx", "csv", "excel", "xlsx", "表格"]):
            return "data_analysis"
        if "总结" in user_input or "摘要" in user_input:
            return "summarize"
        return "unknown"
