from __future__ import annotations

from rag.models import Chunk


class EchoGenerator:
    """回显生成器——v0.2 临时实现。

    把检索片段原样拼成答案，标注来源。不调 LLM，用于验证管线编排。
    真实 LLMGenerator 留 v0.2.5。
    """

    def generate(self, question: str, contexts: list[Chunk]) -> str:
        if not contexts:
            return f"未找到与「{question}」相关的内容。"
        lines = [f"问题：{question}", "相关片段："]
        for i, c in enumerate(contexts, 1):
            lines.append(f"[{i}]（来源 {c.source}）{c.text}")
        return "\n".join(lines)
