from typing import Any

from tools.base_tool import BaseTool


class PlaceholderTool(BaseTool):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "message": "mock result",
            "action_name": action_name,
            "tool_name": self.name,
            "echo": params,
        }
