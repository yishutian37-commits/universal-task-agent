from tools.code_tool import CodeTool
from tools.file_tool import FileTool
from tools.geo_tool import GeoTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.search_tool import SearchTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


def build_tool_registry():
    return {
        "mock_tool": MockTool(),
        "code_tool": CodeTool(),
        "file_tool": FileTool(),
        "geo_tool": GeoTool(),
        "text_tool": TextTool(),
        "table_tool": TableTool(),
        "report_tool": ReportTool(),
        "search_tool": SearchTool(),
    }


TOOL_REGISTRY = build_tool_registry()
