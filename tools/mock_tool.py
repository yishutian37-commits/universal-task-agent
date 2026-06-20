from typing import Any

from tools.base_tool import BaseTool


class MockTool(BaseTool):
    name = "mock_tool"
    description = "V0.1 fixed mock tool for testing the Agent skeleton."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "message": "mock result",
            "action_name": action_name,
            "echo": params,
        }
