from pathlib import Path
import re
from typing import Any

from tools.base_tool import BaseTool


TEXT_EXTENSIONS = (".txt", ".md")
TABLE_EXTENSIONS = (".csv", ".xlsx")


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read local text or table files for UTA tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = str(params.get("user_input", ""))
        file_path = self._find_existing_path(user_input)
        if file_path is None:
            return {
                "message": "已读取文本内容",
                "content": user_input,
                "source_type": "inline",
                "source": "user_input",
                "file_kind": "text",
            }

        if file_path.suffix.lower() in TABLE_EXTENSIONS:
            return {
                "message": "已读取表格文件",
                "source_type": "file",
                "source": str(file_path),
                "file_kind": "table",
            }

        content = file_path.read_text(encoding="utf-8")
        return {
            "message": "已读取文本内容",
            "content": content,
            "source_type": "file",
            "source": str(file_path),
            "file_kind": "text",
        }

    def _find_existing_path(self, text: str) -> Path | None:
        supported_extensions = TEXT_EXTENSIONS + TABLE_EXTENSIONS
        for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", text):
            path = Path(token).expanduser()
            if path.suffix.lower() not in supported_extensions:
                continue
            if path.exists() and path.is_file():
                return path
        return None
