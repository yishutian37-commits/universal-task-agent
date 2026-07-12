from __future__ import annotations

import ast
import os
from pathlib import Path
import re
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
PROJECT_MANIFESTS = [
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
]
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs"}
SKIP_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
MAX_FILES = 40
MAX_CODE_BYTES = 1_000_000

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
        self.project_root = (Path(project_root) if project_root is not None else Path.cwd()).resolve()
        self.key_files = list(key_files) if key_files is not None else None

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name, params
        relative_paths, project_kind = self._scan_targets()
        files = [self._scan_file(relative_path) for relative_path in relative_paths]
        is_uta = project_kind == "uta"
        return {
            "message": "已完成 UTA 代码链路扫描" if is_uta else "已完成项目代码结构扫描",
            "code_analysis": True,
            "project_root": str(self.project_root),
            "project_kind": project_kind,
            "focus": "task_flow" if is_uta else "project_structure",
            "files": files,
            "required_files": list(REQUIRED_FILES) if is_uta else [],
        }

    def _scan_targets(self) -> tuple[list[str], str]:
        if self.key_files is not None:
            is_uta = all((self.project_root / path).is_file() for path in REQUIRED_FILES)
            return self.key_files, "uta" if is_uta else "generic"
        if all((self.project_root / path).is_file() for path in REQUIRED_FILES):
            return [path for path in DEFAULT_KEY_FILES if (self.project_root / path).is_file()], "uta"
        discovered = self._discover_generic_files()
        if not discovered:
            raise ValueError("未发现可分析的项目代码或清单文件")
        return discovered, "generic"

    def _discover_generic_files(self) -> list[str]:
        relative_paths = [name for name in PROJECT_MANIFESTS if (self.project_root / name).is_file()]
        for current_root, directories, filenames in os.walk(self.project_root, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name not in SKIP_DIRECTORIES and not name.startswith(".")
            )
            current = Path(current_root)
            for filename in sorted(filenames):
                path = current / filename
                if path.is_symlink() or path.suffix.lower() not in CODE_EXTENSIONS:
                    continue
                relative = path.relative_to(self.project_root).as_posix()
                if relative not in relative_paths:
                    relative_paths.append(relative)
                if len(relative_paths) >= MAX_FILES:
                    return relative_paths
        return relative_paths

    def _scan_file(self, relative_path: str) -> dict[str, Any]:
        path = self.project_root / relative_path
        if not path.exists() or not path.is_file():
            raise ValueError(f"关键代码文件不存在：{relative_path}")

        if path.stat().st_size > MAX_CODE_BYTES:
            raise ValueError(f"代码文件过大：{relative_path}")
        source = path.read_text(encoding="utf-8")
        role = self._role_for(relative_path)
        if path.suffix.lower() != ".py":
            return {
                "path": relative_path,
                "role": role,
                "imports": self._text_imports(source),
                "classes": self._text_classes(source),
                "functions": self._text_functions(source),
            }
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise ValueError(f"代码文件无法解析：{relative_path}: {exc.msg}") from exc

        return {
            "path": relative_path,
            "role": role,
            "imports": self._imports(tree),
            "classes": self._classes(tree),
            "functions": self._functions(tree),
        }

    def _role_for(self, relative_path: str) -> str:
        if relative_path in ROLE_BY_PATH:
            return ROLE_BY_PATH[relative_path]
        if relative_path in PROJECT_MANIFESTS:
            return "项目清单与依赖配置"
        if Path(relative_path).stem.lower() in {"main", "index", "app", "server", "cli"}:
            return "项目入口或主要源文件"
        return "项目源文件"

    def _text_imports(self, source: str) -> list[str]:
        imports = re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", source)
        imports.extend(re.findall(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", source))
        return list(dict.fromkeys(imports))

    def _text_classes(self, source: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", source)))

    def _text_functions(self, source: str) -> list[str]:
        names = re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", source)
        return list(dict.fromkeys(names))

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
