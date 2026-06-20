from typing import Any


class BaseTool:
    name: str = ""
    description: str = ""

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
