from pathlib import Path
import re
from typing import Any

from tools.base_tool import BaseTool


TEXT_EXTENSIONS = (
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".js",
    ".css",
    ".html",
    ".ini",
    ".cfg",
    ".log",
)
TABLE_EXTENSIONS = (".csv", ".xlsx")
MAX_TEXT_BYTES = 1_000_000
WORKSPACE_CONTEXT_FILES = (
    "README.md",
    "README.txt",
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "main.py",
)


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read local text or table files for UTA tasks."

    def __init__(
        self,
        project_root: Path | str | None = None,
        enforce_project_root: bool | None = None,
    ):
        self.project_root = Path(project_root).expanduser().resolve() if project_root is not None else Path.cwd().resolve()
        self.enforce_project_root = project_root is not None if enforce_project_root is None else bool(enforce_project_root)

    def run(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        del action_name
        user_input = self._current_user_input(str(params.get("user_input", "")))
        if self._looks_like_workspace_listing(user_input):
            return self._list_workspace()
        file_path = self._find_existing_path(user_input)
        if file_path is None:
            missing_path = self._first_supported_path_token(user_input)
            if missing_path is not None:
                raise FileNotFoundError(f"文件不存在：{missing_path}")
            return {
                "message": "已读取文本内容",
                "content": user_input,
                "source_type": "inline",
                "source": "user_input",
                "file_kind": "text",
                "workspace_root": str(self.project_root),
            }

        if file_path.suffix.lower() in TABLE_EXTENSIONS:
            return {
                "message": "已读取表格文件",
                "source_type": "file",
                "source": str(file_path),
                "file_kind": "table",
                "workspace_root": str(self.project_root),
            }

        if file_path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("文件过大，当前最多读取 1 MB 文本")
        content = file_path.read_text(encoding="utf-8")
        return {
            "message": "已读取文本内容",
            "content": content,
            "source_type": "file",
            "source": str(file_path),
            "file_kind": "text",
            "workspace_root": str(self.project_root),
        }

    @staticmethod
    def _current_user_input(user_input: str) -> str:
        matches = list(re.finditer(r"(?:^|\n)当前用户输入[:：]\s*", str(user_input or "")))
        if not matches:
            return str(user_input or "").strip()
        return str(user_input or "")[matches[-1].end() :].strip()

    def _find_existing_path(self, text: str) -> Path | None:
        for token in self._supported_path_tokens(text):
            path = Path(token).expanduser()
            resolved = path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
            if self.enforce_project_root and not self._is_within_project(resolved):
                raise ValueError("不允许读取工作区之外的文件")
            if resolved.exists() and resolved.is_file():
                return resolved
        return None

    def _first_supported_path_token(self, text: str) -> str | None:
        tokens = self._supported_path_tokens(text)
        return tokens[0] if tokens else None

    def _supported_path_tokens(self, text: str) -> list[str]:
        supported_extensions = TEXT_EXTENSIONS + TABLE_EXTENSIONS
        return [
            token
            for token in re.findall(r"[^\s，。！？；：、\"'“”‘’]+", text)
            if Path(token).suffix.lower() in supported_extensions
        ]

    def _looks_like_workspace_listing(self, text: str) -> bool:
        normalized = "".join(str(text or "").lower().split())
        if any(
            marker in normalized
            for marker in (
                "工作区有哪些文件",
                "工作文件夹有哪些文件",
                "列出工作区文件",
                "查看工作区文件",
                "读取工作区目录",
                "列出当前目录",
            )
        ):
            return True
        has_scope = any(
            marker in normalized
            for marker in ("工作区", "工作文件夹", "工作目录", "当前目录", "这个文件夹", "该文件夹")
        )
        has_action = any(marker in normalized for marker in ("读取", "列出", "查看", "有哪些"))
        return has_scope and has_action

    def _list_workspace(self) -> dict[str, Any]:
        entries = []
        children = sorted(self.project_root.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
        for path in children[:200]:
            entries.append(
                {
                    "name": path.name,
                    "path": path.relative_to(self.project_root).as_posix(),
                    "type": "directory" if path.is_dir() else "file",
                }
            )
        listing_lines = [
            f"当前工作区：{self.project_root}",
            "目录内容：",
            *[f"- [{'目录' if item['type'] == 'directory' else '文件'}] {item['path']}" for item in entries],
        ]
        content_parts = ["\n".join(listing_lines)]
        for relative_path in WORKSPACE_CONTEXT_FILES:
            path = self.project_root / relative_path
            if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
                continue
            try:
                file_content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            content_parts.append(f"\n--- 文件：{relative_path} ---\n{file_content}")
        content = "\n".join(content_parts)
        return {
            "message": "\n".join(listing_lines),
            "source_type": "directory",
            "source": str(self.project_root),
            "workspace_root": str(self.project_root),
            "entries": entries,
            "content": content,
            "truncated": len(children) > 200,
        }

    def _is_within_project(self, path: Path) -> bool:
        return path == self.project_root or self.project_root in path.parents
