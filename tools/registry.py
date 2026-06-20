from tools.file_tool import FileTool
from tools.mock_tool import MockTool
from tools.placeholder_tool import PlaceholderTool
from tools.report_tool import ReportTool
from tools.text_tool import TextTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": FileTool(),
    "text_tool": TextTool(),
    "table_tool": PlaceholderTool(
        name="table_tool",
        description="V0.3 placeholder for table analysis steps.",
    ),
    "report_tool": ReportTool(),
}
