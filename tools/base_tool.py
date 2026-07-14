from typing import Any


class BaseTool:
    name: str = ""
    description: str = ""
    default_action: str = "run"
    requires_authorization: bool = False
    action_contracts: dict[str, dict[str, Any]] = {}

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
