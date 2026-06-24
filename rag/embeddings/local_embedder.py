from __future__ import annotations

import os


class LocalEmbedder:
    """bge-small-zh-v1.5 真实语义嵌入（512 维）。

    用 sentence-transformers 加载模型。首次加载需要网络下载模型，
    默认走 hf-mirror.com 镜像（HuggingFace 直连在国内会超时）。
    用户可设 HF_ENDPOINT 环境变量覆盖镜像地址。

    模型加载较重（~1s），适合长生命周期复用，不要每次检索都新建。
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        # 镜像兜底：HuggingFace 直连超时，默认走国内镜像
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [list(v) for v in vectors]
