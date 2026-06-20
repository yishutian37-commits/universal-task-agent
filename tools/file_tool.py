from pathlib import Path
import re
from typing import Any

from tools.base_tool import BaseTool


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read local .txt or .md text for summary tasks."

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = str(params.get("user_input", ""))
        file_path = self._find_existing_text_path(user_input)
        if file_path is None:
            return {
                "message": "已读取文本内容",
                "content": user_input,
                "source_type": "inline",
                "source": "user_input",
            }

        content = file_path.read_text(encoding="utf-8")
        return {
            "message": "已读取文本内容",
            "content": content,
            "source_type": "file",
            "source": str(file_path),
        }

    def _find_existing_text_path(self, text: str) -> Path | None:
        for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", text):
            if not token.endswith((".txt", ".md")):
                continue
            path = Path(token).expanduser()
            if path.exists() and path.is_file():
                return path
        return None
