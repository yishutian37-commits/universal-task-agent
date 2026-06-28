from typing import Any

from llm.llm_client import LLMClient
from tools.base_tool import BaseTool


class TextTool(BaseTool):
    name = "text_tool"
    description = "Summarize text with the configured LLM."

    def __init__(self, llm_client=None):
        self.llm_client = llm_client if llm_client is not None else LLMClient.from_config()

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        source_text = self._source_text(params)
        if not source_text.strip():
            raise ValueError("没有可总结的文本")

        summary = self.llm_client.chat(
            self._system_prompt(),
            self._user_prompt(source_text, params.get("feedback"), params.get("goal")),
        ).strip()
        if not summary:
            raise ValueError("LLM 返回空总结")

        return {
            "message": summary,
            "summary_markdown": summary,
            "source_text": source_text,
        }

    def _source_text(self, params: dict[str, Any]) -> str:
        previous = params.get("previous_result")
        if isinstance(previous, dict) and isinstance(previous.get("content"), str):
            return previous["content"]
        return str(params.get("user_input", ""))

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 UTA 的文本总结工具。只输出中文 Markdown，不要编造原文没有的信息。"
            "如果某类信息没有出现，写“未提及”。"
        )

    @staticmethod
    def _user_prompt(source_text: str, feedback=None, goal=None) -> str:
        feedback_text = ""
        if feedback is not None:
            feedback_text = (
                "\n\n上一次输出未通过校验，请按以下修复建议重新生成：\n"
                f"- {feedback.repair_strategy}\n"
            )
        if isinstance(goal, str) and goal.strip():
            return (
                f"当前步骤目标：{goal.strip()}\n"
                "请围绕当前步骤目标处理下面文本，输出中文 Markdown。"
                "如果原文没有足够信息，明确写“原文未提及”。\n\n"
                f"{feedback_text}"
                f"原文：\n{source_text}"
            )
        return (
            "请总结下面文本，输出固定结构：\n"
            "## 摘要\n"
            "## 核心观点\n"
            "## 关键事实\n"
            "## 待办事项\n"
            "## 风险点\n\n"
            f"{feedback_text}"
            f"原文：\n{source_text}"
        )
