from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool


DEFAULT_KEY_FILES = [
    "main.py",
    "core/task_parser.py",
    "core/planner.py",
    "core/loop.py",
    "core/router.py",
    "core/executor.py",
    "core/verifier.py",
    "core/reflection.py",
    "memory_providers/json_memory_provider.py",
    "core/skill_loader.py",
    "core/skill_builder.py",
    "tools/search_tool.py",
    "tools/report_tool.py",
    "rag/kb.py",
    "desktop/runner.py",
    "desktop/api.py",
]

REQUIRED_FILES = ["main.py", "core/loop.py", "core/router.py", "core/verifier.py"]

ROLE_BY_PATH = {
    "main.py": "CLI 入口与任务运行编排",
    "core/task_parser.py": "任务理解与类型识别",
    "core/planner.py": "把任务拆成不指定工具的目标步骤",
    "core/loop.py": "Agent 主循环、重试、反思和 replan 控制",
    "core/router.py": "根据步骤目标选择工具",
    "core/executor.py": "执行工具并封装 ToolResult",
    "core/verifier.py": "用硬规则校验工具结果和最终报告",
    "core/reflection.py": "分析失败原因并给出修复策略",
    "memory_providers/json_memory_provider.py": "保存任务历史、经验、负向规则和 Skill 候选",
    "core/skill_loader.py": "加载并匹配 Markdown Skill",
    "core/skill_builder.py": "从成功任务中沉淀 Skill 候选",
    "tools/search_tool.py": "搜索、天气等外部信息查询入口",
    "tools/report_tool.py": "把工具结果生成 Markdown 报告",
    "rag/kb.py": "RAG 知识库编排入口",
    "desktop/runner.py": "桌面端后台线程运行核心任务链路",
    "desktop/api.py": "桌面端 JavaScript 到 Python 的桥接 API",
}


class CodeTool(BaseTool):
    name = "code_tool"
    description = "Scan the current UTA project code for task-flow reading reports."

    def __init__(
        self,
        project_root: Path | str | None = None,
        key_files: list[str] | None = None,
    ):
        self.project_root = Path(project_root) if project_root is not None else Path.cwd()
        self.key_files = list(key_files) if key_files is not None else list(DEFAULT_KEY_FILES)

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name, params
        files = [self._scan_file(relative_path) for relative_path in self.key_files]
        return {
            "message": "已完成 UTA 代码链路扫描",
            "code_analysis": True,
            "project_root": str(self.project_root),
            "focus": "task_flow",
            "files": files,
            "required_files": list(REQUIRED_FILES),
        }

    def _scan_file(self, relative_path: str) -> dict[str, Any]:
        path = self.project_root / relative_path
        if not path.exists() or not path.is_file():
            raise ValueError(f"关键代码文件不存在：{relative_path}")

        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise ValueError(f"代码文件无法解析：{relative_path}: {exc.msg}") from exc

        return {
            "path": relative_path,
            "role": ROLE_BY_PATH.get(relative_path, "UTA 代码文件"),
            "imports": self._imports(tree),
            "classes": self._classes(tree),
            "functions": self._functions(tree),
        }

    def _imports(self, tree: ast.AST) -> list[str]:
        imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports

    def _classes(self, tree: ast.AST) -> list[str]:
        return [node.name for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)]

    def _functions(self, tree: ast.AST) -> list[str]:
        function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
        return [node.name for node in ast.iter_child_nodes(tree) if isinstance(node, function_types)]
