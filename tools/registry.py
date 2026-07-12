from __future__ import annotations

from pathlib import Path

from desktop.paths import resource_path, uta_home
from tools.base_tool import BaseTool
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.langchain_adapter import LangChainToolAdapter
from tools.langchain_common_tools import (
    DirectoryCreateLangChainTool,
    FileDeleteLangChainTool,
    FileWriteLangChainTool,
    PythonReplLangChainTool,
    ShellLangChainTool,
    build_common_langchain_tools,
)
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


class _EchoLangChainTool:
    name = "langchain_echo_tool"
    description = "Safe demo LangChain-style tool that echoes its structured input."

    def invoke(self, tool_input):
        return {"echo": tool_input}


def build_tool_registry(
    project_root: Path | str | None = None,
    skills_root: Path | str | None = None,
    memory_root: Path | str | None = None,
    enable_langchain_tools: bool = True,
    langchain_tools: list | tuple | None = None,
    enable_dangerous_tools: bool = False,
    authorization_manager=None,
    dangerous_allowed_roots: list | tuple | None = None,
) -> dict[str, BaseTool]:
    """构造工具注册表。

    参数用于桌面端等需要指定资源根目录的场景；CLI/默认场景不传参即可。
    """
    explicit_project_root = project_root is not None
    if project_root is not None:
        project_root = Path(project_root)
    else:
        project_root = Path.cwd()

    if skills_root is not None:
        skills_root = Path(skills_root)
    else:
        skills_root = project_root / "skills"

    if memory_root is not None:
        memory_root = Path(memory_root)
    else:
        memory_root = uta_home() / "memory"

    geo_vendor_root = skills_root / "vendor" / "geo-agent-marketing-optimized"

    search_tool = SearchTool()
    registry = {
        "code_tool": CodeTool(project_root=project_root),
        "file_tool": FileTool(project_root=project_root, enforce_project_root=explicit_project_root),
        "geo_tool": GeoTool(geo_vendor_root),
        "history_tool": HistoryTool(memory_root=memory_root),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": search_tool,
    }
    if enable_langchain_tools:
        common_tools = (_EchoLangChainTool(),) + build_common_langchain_tools(search_tool=search_tool)
        if enable_dangerous_tools:
            common_tools = common_tools + (
                ShellLangChainTool(
                    authorization_manager=authorization_manager,
                    enabled=True,
                    allowed_roots=list(dangerous_allowed_roots or [project_root]),
                ),
                FileWriteLangChainTool(
                    authorization_manager=authorization_manager,
                    enabled=True,
                    allowed_roots=list(dangerous_allowed_roots or [project_root]),
                ),
                PythonReplLangChainTool(
                    authorization_manager=authorization_manager,
                    enabled=True,
                    allowed_roots=list(dangerous_allowed_roots or [project_root]),
                ),
                FileDeleteLangChainTool(
                    authorization_manager=authorization_manager,
                    enabled=True,
                    allowed_roots=list(dangerous_allowed_roots or [project_root]),
                ),
                DirectoryCreateLangChainTool(
                    authorization_manager=authorization_manager,
                    enabled=True,
                    allowed_roots=list(dangerous_allowed_roots or [project_root]),
                ),
            )
        for tool in langchain_tools or common_tools:
            adapted = LangChainToolAdapter(tool)
            registry[adapted.name] = adapted
    return registry


TOOL_REGISTRY = build_tool_registry()
