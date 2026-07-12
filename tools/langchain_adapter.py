from __future__ import annotations

import json
from typing import Any

from tools.base_tool import BaseTool


class LangChainToolAdapter(BaseTool):
    """把 LangChain tool 适配成 UTA 的 BaseTool 接口。"""

    def __init__(
        self,
        langchain_tool: Any,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self.langchain_tool = langchain_tool
        self.name = name or str(getattr(langchain_tool, "name", "") or langchain_tool.__class__.__name__)
        self.description = description or str(getattr(langchain_tool, "description", "") or "")

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        tool_input = self._tool_input_from_params(params)
        try:
            output = self.langchain_tool.invoke(tool_input)
        except Exception as exc:
            raise RuntimeError(f"LangChain 工具执行失败：{exc}") from exc

        result = {
            "message": f"LangChain 工具执行完成：{self._format_output(output)}",
            "tool": self.name,
            "output": output,
        }
        if isinstance(output, dict):
            for key, value in output.items():
                result.setdefault(str(key), value)
        return result

    def _tool_input_from_params(self, params: dict[str, Any]) -> Any:
        if "tool_input" in params:
            return params["tool_input"]

        for key in ("query", "user_input", "goal"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                return {"query": value.strip()}

        return {"query": ""}

    def _format_output(self, output: Any) -> str:
        if isinstance(output, str):
            return output
        return json.dumps(output, ensure_ascii=False)
