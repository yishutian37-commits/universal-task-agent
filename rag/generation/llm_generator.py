from __future__ import annotations

from rag.models import Chunk

SYSTEM_PROMPT = (
    "你是一个知识库问答助手。根据提供的检索片段回答用户问题。"
    "回答要基于片段内容，不要编造。如果片段不足以回答，明确说明。"
    "在答案中用 [1][2] 等标注引用了哪些来源片段。"
)


class LLMGenerator:
    """基于 LLM 的答案生成器，复用 UTA 的 LLMClient。

    默认用 LLMClient.from_config()（读 .env 的 mimo 配置）。
    测试时可注入 fake client，不碰网络。
    """

    def __init__(self, client=None) -> None:
        if client is None:
            from llm.llm_client import LLMClient

            client = LLMClient.from_config()
        self._client = client

    def generate(self, question: str, contexts: list[Chunk]) -> str:
        user_prompt = self._build_user_prompt(question, contexts)
        return self._client.chat(SYSTEM_PROMPT, user_prompt)

    def _build_user_prompt(self, question: str, contexts: list[Chunk]) -> str:
        lines = [f"问题：{question}"]
        if contexts:
            lines.append("检索到的相关片段：")
            for i, c in enumerate(contexts, 1):
                lines.append(f"[{i}]（来源 {c.source}）{c.text}")
        else:
            lines.append("（未检索到相关片段）")
        lines.append("请根据以上片段回答问题。")
        return "\n".join(lines)
