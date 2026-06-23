from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from rag.errors import UnsupportedSourceError


@dataclass
class LoadedDoc:
    """Loader 解析后的文档：纯文本 + 来源 + 元数据。"""

    text: str
    source: str
    metadata: dict = field(default_factory=dict)


class BaseLoader(ABC):
    """文档加载器接口。按扩展名/来源类型路由实现。"""

    @abstractmethod
    def load(self, source: str) -> LoadedDoc:
        """读取来源（文件路径/URL），返回纯文本和元数据。"""


class LoaderFactory:
    """按文件扩展名选择 Loader。未识别类型抛 UnsupportedSourceError。"""

    def __init__(self, loaders: dict[str, BaseLoader]):
        self._loaders = loaders

    def get(self, source: str) -> BaseLoader:
        ext = os.path.splitext(source)[1].lower()
        loader = self._loaders.get(ext)
        if loader is None:
            raise UnsupportedSourceError(
                f"不支持的文件类型 {ext or '(无扩展名)'}，"
                f"当前支持：{sorted(self._loaders.keys())}"
            )
        return loader
