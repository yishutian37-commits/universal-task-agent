from __future__ import annotations

import re


_KNOWLEDGE_CONTAINER = re.compile(r"(?:从|在)?知识库(?:中|里|内|里面)")
_LEADING_WRAPPERS = (
    re.compile(r"^(?:请|麻烦|能否|可以)?(?:你)?(?:帮我)?\s*"),
    re.compile(r"^(?:把|将)\s*"),
    re.compile(r"^(?:请)?(?:逐字)?(?:发给我|发送给我|提供给我|给我看)\s*"),
    re.compile(
        r"^(?:给我)?(?:查找|检索|搜索|找出|找一下|介绍一下|介绍|"
        r"讲解一下|讲解|整理一下|整理|展示一下|展示|看一下|看看)\s*"
    ),
    re.compile(r"^(?:关于|有关)\s*"),
)
_TRAILING_WRAPPERS = (
    re.compile(r"\s*(?:发给我|发送给我|提供给我|展示给我|给我看|告诉我)$"),
    re.compile(
        r"\s*(?:的)?(?:完整原文|原始内容|完整章节|完整内容|详细内容|"
        r"相关知识|相关内容|相关资料|相关信息|原文|全文|部分|章节|资料|内容)$"
    ),
)


def normalize_knowledge_query(question: str) -> str:
    """去掉“发给我”一类交付语，只保留需要检索的核心主题。"""
    original = re.sub(r"\s+", " ", str(question or "")).strip()
    if not original:
        return ""

    text = _KNOWLEDGE_CONTAINER.sub(" ", original)
    text = re.sub(r"\s+", " ", text).strip(" 。，！？!?;:；：")

    changed = True
    while changed and text:
        changed = False
        for pattern in _LEADING_WRAPPERS:
            updated = pattern.sub("", text, count=1).strip()
            if updated != text:
                text = updated
                changed = True

    changed = True
    while changed and text:
        changed = False
        for pattern in _TRAILING_WRAPPERS:
            updated = pattern.sub("", text, count=1).strip()
            if updated != text:
                text = updated
                changed = True

    text = re.sub(r"\s+", " ", text).strip(" 。，！？!?;:；：")
    return text or original


def expand_knowledge_query(question: str) -> str:
    """根据通用问法补充检索词，不修改用户的主题。"""
    query = normalize_knowledge_query(question)
    if not query:
        return ""

    additions: tuple[str, ...] = ()
    compact = "".join(query.split())
    if re.search(r"(?:如何|怎么|怎样).{0,8}(?:构建|搭建|创建|实现|开发|配置)", compact):
        additions = ("基础流程", "核心步骤", "架构")
    elif "是什么" in compact or "什么是" in compact:
        additions = ("定义", "核心概念")
    elif any(marker in compact for marker in ("区别", "差别", "不同", "差异")):
        additions = ("对比", "差异")

    missing = [term for term in additions if term not in query]
    return " ".join([query, *missing]).strip()
