from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DirectChatResponse:
    category: str
    content: str


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


def direct_chat_response(text: str) -> DirectChatResponse | None:
    if chat_route_kind(text) != "direct":
        return None

    normalized = _normalize(text)

    if _contains_any(normalized, GREETING_MARKERS):
        return DirectChatResponse("greeting", _greeting_answer())
    if _contains_any(normalized, IDENTITY_MARKERS):
        return DirectChatResponse("identity", _identity_answer())
    if _contains_any(normalized, CAPABILITY_MARKERS):
        return DirectChatResponse("capability", _capability_answer())
    if _contains_any(normalized, USAGE_MARKERS):
        return DirectChatResponse("usage", _usage_answer())
    if _contains_any(normalized, STATUS_MARKERS):
        return DirectChatResponse("status", _status_answer())

    return None


def chat_route_kind(text: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        return "empty"
    if _looks_like_task(normalized):
        return "task"
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
    return _contains_any(normalized, TASK_MARKERS)


def _greeting_answer() -> str:
    return "\n".join(
        [
            "你好，我是 UTA。",
            "",
            "你可以直接把任务发给我，我会先判断这是普通对话还是需要执行的任务。",
            "如果是任务，我会拆解步骤、调用工具、显示过程，并把结果保存到本地历史。",
        ]
    )


def _identity_answer() -> str:
    return "\n".join(
        [
            "我是 UTA，一个本地运行的学习型 Agent 桌面应用。",
            "",
            "我不是只做普通聊天；更擅长把任务拆成步骤，调用文本、表格、搜索、代码阅读、RAG、GEO 等工具执行，再把过程和结果保存下来。",
        ]
    )


def _capability_answer() -> str:
    return "\n".join(
        [
            "## 我现在能做什么",
            "",
            "- 文本总结：把文章或资料整理成结构化中文总结。",
            "- 表格分析：读取 CSV / Excel，输出字段说明、统计、异常和建议。",
            "- 联网调研：搜索资料并生成带来源的调研报告。",
            "- 实时天气：识别天气问题并返回当前天气。",
            "- 代码阅读：只读分析当前项目结构、调用链和关键文件。",
            "- RAG 知识库：摄入本地文档后做检索和问答。",
            "- GEO 分析：基于已接入的 GEO skill 包生成问题矩阵、内容 Brief 和合规建议。",
            "- 历史任务查询：列出你之前让我做过的任务。",
            "- 复杂任务拆解：把复杂任务拆成步骤，逐步执行并显示进度。",
        ]
    )


def _usage_answer() -> str:
    return "\n".join(
        [
            "## 怎么用",
            "",
            "直接在底部输入框发送任务即可。",
            "",
            "可以试这些示例：",
            "- 帮我总结一段文本：...",
            "- 分析 examples/orders.csv",
            "- 调研包头今日天气状况",
            "- 阅读当前项目代码，说明任务链路",
            "- 帮我执行复杂任务：[1]总结文章 [2]提炼结论 [3]改写成小白版",
        ]
    )


def _status_answer() -> str:
    return "\n".join(
        [
            "桌面端可以看到这些状态：",
            "",
            "- 对话消息流：你发的消息和我的回复。",
            "- 执行步骤：每一步会显示 `[ ]`、`[...]`、`[x]` 或 `[!]`。",
            "- 实时日志：解析、规划、路由、执行、校验等过程。",
            "- state.json：当前任务的结构化状态。",
            "- 会话历史、记忆、知识库和技能包页面。",
        ]
    )
