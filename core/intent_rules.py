from __future__ import annotations

import re


FILE_EXTENSIONS = (
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
    ".csv",
    ".xlsx",
)
WORKSPACE_FILE_MARKERS = (
    "工作区有哪些文件",
    "工作文件夹有哪些文件",
    "列出工作区文件",
    "查看工作区文件",
    "读取工作区",
)
DANGEROUS_TOOL_MARKERS = (
    "shell",
    "终端命令",
    "执行命令",
    "运行命令",
    "python代码",
    "pythonrepl",
    "repl",
    "写入文件",
    "创建文件",
    "覆盖文件",
    "追加文件",
    "删除文件",
    "删除目录",
    "删除本地文件",
    "移除文件",
    "移除目录",
    "移除本地文件",
    "新建文件夹",
    "创建文件夹",
    "新建目录",
    "创建目录",
    "mkdir",
)


def compact_text(text: str) -> str:
    return "".join(str(text or "").strip().lower().split())


def looks_like_workspace_file_request(text: str) -> bool:
    normalized = compact_text(text)
    if any(compact_text(marker) in normalized for marker in WORKSPACE_FILE_MARKERS):
        return True
    has_scope = any(
        marker in normalized
        for marker in ("工作区", "工作文件夹", "工作目录", "当前目录", "这个文件夹", "该文件夹")
    )
    has_action = any(marker in normalized for marker in ("读取", "列出", "查看", "有哪些"))
    return has_scope and has_action


def looks_like_named_file_read(text: str) -> bool:
    lowered = str(text or "").lower()
    return "读取" in str(text or "") and any(extension in lowered for extension in FILE_EXTENSIONS)


def looks_like_directory_create(text: str) -> bool:
    normalized = compact_text(text)
    return "mkdir" in normalized or (
        any(marker in normalized for marker in ("创建", "新建"))
        and any(marker in normalized for marker in ("文件夹", "目录"))
    )


def looks_like_dangerous_tool_request(text: str) -> bool:
    normalized = compact_text(text)
    has_directory_create = "mkdir" in normalized or (
        any(marker in normalized for marker in ("创建", "新建"))
        and any(marker in normalized for marker in ("文件夹", "目录"))
    )
    return has_directory_create or any(marker in normalized for marker in DANGEROUS_TOOL_MARKERS)


def looks_like_desktop_directory_request(text: str) -> bool:
    normalized = compact_text(text)
    return "桌面" in normalized and looks_like_directory_create(normalized)


def looks_like_langchain_tool_task(text: str) -> bool:
    lowered = str(text or "").lower()
    if looks_like_workspace_file_request(text) or looks_like_named_file_read(text):
        return True
    if "langchain" in lowered and ("工具" in text or "tool" in lowered or "回显" in text):
        return True
    if looks_like_dangerous_tool_request(text) or looks_like_directory_create(text):
        return True
    if any(marker in text for marker in ("计算", "算一下", "等于多少")):
        return True
    if any(marker in text for marker in ("现在几点", "当前时间", "今天日期", "当前日期")):
        return True
    if "json" in lowered and any(marker in text for marker in ("解析", "格式化", "提取", "校验")):
        return True
    if "http get" in lowered or re.search(r"https?://", str(text or "")):
        return any(marker in lowered for marker in ("http", "get", "抓取", "请求", "访问"))
    return False


def langchain_tool_name(text: str) -> str | None:
    lowered = str(text or "").lower()
    if looks_like_workspace_file_request(text) or looks_like_named_file_read(text):
        return "file_tool"
    if any(marker in text for marker in ("天气", "气温", "温度")):
        return "langchain_weather_tool"
    if looks_like_directory_create(text):
        return "langchain_directory_create_tool"
    if any(marker in text for marker in ("删除文件", "删除目录", "删除本地文件", "移除文件", "移除目录", "移除本地文件")):
        return "langchain_file_delete_tool"
    if any(marker in text for marker in ("写入文件", "创建文件", "覆盖文件", "追加文件")):
        return "langchain_file_write_tool"
    if any(marker in lowered for marker in ("shell", "执行命令", "运行命令", "终端命令")):
        return "langchain_shell_tool"
    if "python" in lowered or "repl" in lowered:
        return "langchain_python_repl_tool"
    if any(marker in text for marker in ("搜索", "查找", "调研")):
        return "langchain_search_tool"
    if "http get" in lowered or "https://" in lowered or "http://" in lowered:
        return "langchain_http_get_tool"
    if "json" in lowered:
        return "langchain_json_tool"
    if any(marker in text for marker in ("现在几点", "当前时间", "今天日期", "当前日期")):
        return "langchain_datetime_tool"
    if any(marker in text for marker in ("计算", "算一下", "等于多少")):
        return "langchain_calculator_tool"
    if "回显" in text:
        return "langchain_echo_tool"
    return None
