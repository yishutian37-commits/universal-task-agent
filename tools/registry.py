from __future__ import annotations

from pathlib import Path

from desktop.paths import resource_path, uta_home
from tools.base_tool import BaseTool
from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.history_tool import HistoryTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry(
    project_root: Path | str | None = None,
    skills_root: Path | str | None = None,
    memory_root: Path | str | None = None,
) -> dict[str, BaseTool]:
    """构造工具注册表。

    参数用于桌面端等需要指定资源根目录的场景；CLI/默认场景不传参即可。
    """
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

    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(project_root=project_root),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(geo_vendor_root),
        "history_tool": HistoryTool(memory_root=memory_root),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
