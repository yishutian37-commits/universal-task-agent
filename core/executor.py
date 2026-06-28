from tools.registry import build_tool_registry

from core.state import Action, ToolResult


class Executor:
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry if tool_registry is not None else build_tool_registry()

    def run(self, action: Action) -> ToolResult:
        tool = self.tool_registry.get(action.tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                tool_name=action.tool_name,
                action_name=action.action_name,
                result={},
                error=f"tool_unavailable: {action.tool_name}",
                step_id=action.step_id,
            )

        try:
            result = tool.run(action.action_name, action.params)
        except Exception as exc:
            return ToolResult(
                success=False,
                tool_name=action.tool_name,
                action_name=action.action_name,
                result={},
                error=f"tool_error: {exc}",
                step_id=action.step_id,
            )

        return ToolResult(
            success=True,
            tool_name=action.tool_name,
            action_name=action.action_name,
            result=result,
            error=None,
            step_id=action.step_id,
        )
