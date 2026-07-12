from __future__ import annotations

from core.intent_rules import looks_like_langchain_tool_task, looks_like_workspace_file_request


TASK_MARKERS = [
    "帮我总结",
    "帮我写",
    "帮我做",
    "请分析",
    "请总结",
    "请帮我",
    "总结一段",
    "分析 ",
    "分析/",
    "分析：",
    "分析 examples",
    "调研",
    "搜索",
    "查找",
    "今日天气",
    "天气状况",
    "执行复杂任务",
    "复杂任务",
    "分步骤",
    "阅读当前项目",
    "阅读代码",
    "代码阅读",
    "做 geo",
    "geo 分析",
    "GEO 分析",
    "历史任务",
    "任务历史",
    "之前让你",
    "做过什么任务",
    "进行过什么任务",
]

GREETING_MARKERS = [
    "你好",
    "您好",
    "hi",
    "hello",
    "在吗",
]

IDENTITY_MARKERS = [
    "你是谁",
    "你是什么",
    "介绍一下你",
    "你叫什么",
]

CAPABILITY_MARKERS = [
    "你能干什么",
    "你可以干什么",
    "你会干什么",
    "你有什么功能",
    "能做什么",
    "可以做什么",
    "有哪些功能",
    "当前项目能干什么",
    "这个应用能干什么",
]

USAGE_MARKERS = [
    "怎么用",
    "如何使用",
    "使用方法",
    "怎么开始",
    "给我示例",
    "示例任务",
]

STATUS_MARKERS = [
    "能看到哪些状态",
    "看到什么状态",
    "执行状态",
    "桌面端能看到",
    "有什么页面",
]

CONTEXTUAL_MARKERS = [
    "刚才",
    "刚刚",
    "前面",
    "前文",
    "上面",
    "之前",
    "上一条",
    "前一条",
    "记得我",
    "继续刚才",
]


def chat_route_kind(text: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        return "empty"
    if _looks_like_task(normalized):
        return "task"
    if _looks_like_contextual_turn(normalized):
        return "chat"
    if _contains_any(normalized, GREETING_MARKERS):
        return "direct"
    if _contains_any(normalized, IDENTITY_MARKERS):
        return "direct"
    if _contains_any(normalized, CAPABILITY_MARKERS):
        return "direct"
    if _contains_any(normalized, USAGE_MARKERS):
        return "direct"
    if _contains_any(normalized, STATUS_MARKERS):
        return "direct"
    return "chat"


def _normalize(text: str) -> str:
    return "".join(str(text or "").strip().lower().split())


def _contains_any(normalized: str, markers: list[str]) -> bool:
    return any(_normalize(marker) in normalized for marker in markers)


def _looks_like_task(normalized: str) -> bool:
    if looks_like_langchain_tool_task(normalized) or looks_like_workspace_file_request(normalized):
        return True
    if _contains_any(normalized, TASK_MARKERS):
        return True
    if "读取" in normalized and any(
        extension in normalized
        for extension in (".txt", ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".js", ".css", ".html", ".ini", ".cfg", ".log", ".csv", ".xlsx")
    ):
        return True
    if any(marker in normalized for marker in ("读取", "列出", "查看", "有哪些")) and any(
        marker in normalized
        for marker in ("工作区", "工作文件夹", "工作目录", "当前目录", "这个文件夹", "该文件夹")
    ):
        return True
    return (
        any(marker in normalized for marker in ("创建", "新建"))
        and any(marker in normalized for marker in ("文件夹", "目录"))
    )


def _looks_like_contextual_turn(normalized: str) -> bool:
    return _contains_any(normalized, CONTEXTUAL_MARKERS)
