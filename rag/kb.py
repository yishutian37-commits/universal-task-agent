from __future__ import annotations

import os
import re
import uuid
from dataclasses import replace
from datetime import datetime

from rag.chunkers.base import BaseChunker
from rag.embeddings.base import BaseEmbedder
from rag.errors import EmptyStoreError
from rag.generation.base import BaseGenerator
from rag.loaders.base import LoaderFactory
from rag.models import Answer, Document, RetrievedChunk
from rag.query_normalizer import expand_knowledge_query
from rag.retrieval.base import BaseRetriever
from rag.store.base import BaseVectorStore


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class KnowledgeBase:
    """RAG 知识库编排类——唯一知道全部六层的入口。

    UTA 未来接入只需实例化本类，调用 ingest_path / query / ask。
    """

    def __init__(
        self,
        loader_factory: LoaderFactory,
        chunker: BaseChunker,
        embedder: BaseEmbedder,
        store: BaseVectorStore,
        retriever: BaseRetriever,
        generator: BaseGenerator,
        reranker=None,
    ) -> None:
        self.loader_factory = loader_factory
        self.chunker = chunker
        self.embedder = embedder
        self._store = store
        self.retriever = retriever
        self.generator = generator
        if reranker is None:
            from rag.retrieval.reranker import KeywordDiversityReranker

            reranker = KeywordDiversityReranker()
        self.reranker = reranker

    @classmethod
    def from_config(cls, db_path: str = "data/knowledge.db") -> "KnowledgeBase":
        """无参装配：用 v0.2 默认组件创建实例。"""
        from rag.defaults import create_default_kb

        return create_default_kb(db_path=db_path)

    def ingest_path(self, source: str) -> dict:
        """摄入单个来源（文件路径）：加载→切片→嵌入→存储，幂等。"""
        loader = self.loader_factory.get(source)
        loaded = loader.load(source)

        existing_doc = next(
            (document for document in self._store.list_docs() if document.source == source),
            None,
        )
        doc_id = existing_doc.doc_id if existing_doc is not None else str(uuid.uuid4())
        # 幂等：复用同源文档身份，并替换旧 chunk。
        self._store.delete_by_source(source)

        chunks = self.chunker.chunk_text(loaded.text, doc_id, source)
        vectors = self.embedder.embed([c.text for c in chunks])
        self._store.add(chunks, vectors)

        doc = Document(
            doc_id=doc_id,
            source=source,
            title=loaded.metadata.get("title", os.path.basename(source)),
            type=loaded.metadata.get("type", os.path.splitext(source)[1].lstrip(".")),
            chunk_count=len(chunks),
            ingested_at=_now_iso(),
            metadata=loaded.metadata,
        )
        self._store.upsert_doc(doc)

        return {"doc_id": doc_id, "chunk_count": len(chunks), "source": source}

    def query(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        """只检索，返回 top-k 片段（不调 LLM）。空库抛 EmptyStoreError。"""
        if self._store.count() == 0:
            raise EmptyStoreError("知识库为空，请先 ingest 文档")

        retrieval_query = expand_knowledge_query(question)
        query_vec = self.embedder.embed([retrieval_query])[0]
        vectors, chunks = self._store.all_vectors()
        if not chunks:
            raise EmptyStoreError("知识库为空，请先 ingest 文档")
        candidate_k = min(len(chunks), max(top_k * 12, 48))
        hybrid_search = getattr(self.retriever, "search_with_text", None)
        if callable(hybrid_search):
            candidates = hybrid_search(vectors, chunks, query_vec, retrieval_query, candidate_k)
        else:
            candidates = self.retriever.search(vectors, chunks, query_vec, candidate_k)
        return self.reranker.rerank(retrieval_query, candidates, top_k)

    def query_with_neighbors(
        self,
        question: str,
        *,
        top_k: int = 4,
        neighbor_window: int = 4,
        max_sources: int = 2,
        max_chars: int = 16_000,
        min_source_score_ratio: float = 0.82,
    ) -> list[RetrievedChunk]:
        """检索后展开命中片段的同源相邻内容，供完整章节类请求使用。"""
        hits = self.query(question, top_k=top_k)
        _, all_chunks = self._store.all_vectors()
        if not hits or not all_chunks:
            return hits

        source_order: list[tuple[str, str]] = []
        source_scores: dict[tuple[str, str], float] = {}
        hit_indexes: dict[tuple[str, str], dict[int, float]] = {}
        for hit in hits:
            key = (hit.chunk.doc_id, hit.chunk.source)
            if key not in source_scores:
                source_order.append(key)
                source_scores[key] = float(hit.score)
                hit_indexes[key] = {}
            source_scores[key] = max(source_scores[key], float(hit.score))
            chunk_index = int(hit.chunk.chunk_index)
            hit_indexes[key][chunk_index] = max(
                hit_indexes[key].get(chunk_index, float("-inf")),
                float(hit.score),
            )

        best_score = max(source_scores.values(), default=0.0)
        if best_score > 0:
            ratio = min(1.0, max(0.0, float(min_source_score_ratio)))
            minimum_score = best_score * ratio
            eligible_sources = [
                key for key in source_order if source_scores[key] >= minimum_score
            ]
        else:
            # 非正分值无法用比例衡量可信度，仅保留最优来源。
            eligible_sources = source_order[:1]
        selected_sources = eligible_sources[: max(1, int(max_sources))]

        window = max(0, int(neighbor_window))
        char_limit = max(1, int(max_chars))
        total_chars = 0
        expanded: list[RetrievedChunk] = []
        for key in selected_sources:
            scored_indexes = hit_indexes[key]
            best_index = max(
                scored_indexes,
                key=lambda index: (scored_indexes[index], -index),
            )
            candidates = sorted(
                (
                    chunk
                    for chunk in all_chunks
                    if (chunk.doc_id, chunk.source) == key
                    and abs(int(chunk.chunk_index) - best_index) <= window
                ),
                key=lambda chunk: int(chunk.chunk_index),
            )
            for chunk in candidates:
                remaining = char_limit - total_chars
                if remaining <= 0:
                    break
                text = str(chunk.text or "")
                if len(text) > remaining:
                    text = text[:remaining]
                expanded.append(
                    RetrievedChunk(
                        chunk=replace(chunk, text=text),
                        score=source_scores[key],
                    )
                )
                total_chars += len(text)
            if total_chars >= char_limit:
                break
        return expanded or hits

    def ask(self, question: str, top_k: int = 5) -> Answer:
        """端到端问答：检索 → 生成，返回带来源引用的答案。"""
        retrieved = self.query(question, top_k=top_k)
        contexts = [r.chunk for r in retrieved]
        answer_text = self.generator.generate(question, contexts)
        return Answer(answer=answer_text, sources=retrieved)

    def list_docs(self) -> list[Document]:
        """列出库内所有文档。"""
        return self._store.list_docs()

    def stats(self) -> dict:
        """返回库统计：文档数、chunk 数、维度。"""
        docs = self._store.list_docs()
        return {
            "documents": len(docs),
            "chunks": self._store.count(),
            "dim": self.embedder.dim,
        }

    def delete(self, target: str) -> dict:
        """按 doc_id 或 source 删除文档。返回删除条数和目标。"""
        source_doc = next(
            (document for document in self._store.list_docs() if document.source == target),
            None,
        )
        doc_id = source_doc.doc_id if source_doc is not None else target
        deleted = self._store.delete_doc(doc_id)
        return {"deleted": deleted, "target": target}

    def rebuild(self) -> dict:
        """清空库（换 embedder 后重建用）。返回清空后的统计。"""
        self._store.clear()
        return self.stats()


def _lexical_overlap(question: str, text: str) -> float:
    query_tokens = _search_tokens(question)
    if not query_tokens:
        return 0.0
    text_tokens = _search_tokens(text)
    return len(query_tokens & text_tokens) / len(query_tokens)


def _search_tokens(value: str) -> set[str]:
    normalized = str(value or "").casefold()
    ascii_words = set(re.findall(r"[a-z0-9_]{2,}", normalized))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    chinese_tokens: set[str] = set()
    for run in chinese_runs:
        chinese_tokens.update(run)
        chinese_tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return ascii_words | chinese_tokens
