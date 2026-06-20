from tools.mock_tool import MockTool
from tools.placeholder_tool import PlaceholderTool


TOOL_REGISTRY = {
    "mock_tool": MockTool(),
    "file_tool": PlaceholderTool(
        name="file_tool",
        description="V0.3 placeholder for reading files or inline input.",
    ),
    "text_tool": PlaceholderTool(
        name="text_tool",
        description="V0.3 placeholder for text processing steps.",
    ),
    "table_tool": PlaceholderTool(
        name="table_tool",
        description="V0.3 placeholder for table analysis steps.",
    ),
    "report_tool": PlaceholderTool(
        name="report_tool",
        description="V0.3 placeholder for report generation steps.",
    ),
}
