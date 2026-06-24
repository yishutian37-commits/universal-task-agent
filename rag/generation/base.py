from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk


class BaseGenerator(ABC):
    """答案生成接口。基于检索片段和问题，生成带引用的答案。"""

    @abstractmethod
    def generate(self, question: str, contexts: list[Chunk]) -> str:
        """根据问题上下文片段生成答案文本。"""
