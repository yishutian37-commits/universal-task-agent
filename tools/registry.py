from tools.file_tool import FileTool
from tools.mock_tool import MockTool
from tools.report_tool import ReportTool
from tools.table_tool import TableTool
from tools.text_tool import TextTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": FileTool(),
    "text_tool": TextTool(),
    "table_tool": TableTool(),
    "report_tool": ReportTool(),
}
