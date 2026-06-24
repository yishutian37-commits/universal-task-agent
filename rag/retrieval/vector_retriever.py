from __future__ import annotations

import numpy as np

from rag.models import Chunk, RetrievedChunk


class VectorRetriever:
    """numpy 余弦相似度检索。

    余弦相似度 = (A·B) / (|A|·|B|)。输入全量向量和查询向量，
    返回按相似度降序的 top-k。无状态，纯函数式。
    """

    def search(
        self,
        vectors: list[list[float]],
        chunks: list[Chunk],
        query_vec: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not vectors:
            return []

        mat = np.asarray(vectors, dtype=np.float32)  # (N, D)
        q = np.asarray(query_vec, dtype=np.float32)  # (D,)

        mat_norms = np.linalg.norm(mat, axis=1, keepdims=True)
        q_norm = np.linalg.norm(q)
        mat_normed = mat / np.clip(mat_norms, 1e-10, None)
        q_normed = q / max(q_norm, 1e-10)

        similarities = mat_normed @ q_normed  # (N,)
        k = min(top_k, len(vectors))
        top_idx = np.argpartition(similarities, -k)[-k:]
        top_idx = top_idx[np.argsort(similarities[top_idx])[::-1]]

        return [
            RetrievedChunk(chunk=chunks[i], score=float(similarities[i]))
            for i in top_idx
        ]
