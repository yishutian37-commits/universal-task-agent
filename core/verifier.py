from core.state import CheckResult, ToolResult


class Verifier:
    def check(self, result: ToolResult) -> CheckResult:
        if result.success:
            return CheckResult(passed=True, failed_reasons=[], suggested_fix=[])

        error = result.error or "unknown error"
        return CheckResult(
            passed=False,
            failed_reasons=[f"工具执行失败：{error}"],
            suggested_fix=["检查工具名称或工具实现"],
        )
