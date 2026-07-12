from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from rag.errors import EmptyStoreError, KnowledgeBaseError
from rag.kb import KnowledgeBase

app = FastAPI(title="RAG 知识库 API", version="0.4.0")

# 全局 KB 实例，启动时创建。通过环境变量配置路径和模型模式。
_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        db_path = os.getenv("KB_DB_PATH", "data/knowledge.db")
        use_real = os.getenv(
            "KB_USE_REAL_MODELS",
            os.getenv("KB_USE_REAL_MODES", "0"),
        ) == "1"
        from rag.defaults import create_default_kb

        _kb = create_default_kb(db_path=db_path, use_real_models=use_real)
    return _kb


def set_kb(kb: KnowledgeBase) -> None:
    """测试用：注入自定义 KB 实例。"""
    global _kb
    _kb = kb


# ---- 请求/响应模型 ----


class IngestRequest(BaseModel):
    path: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    expand: bool = False
    neighbor_window: int = 4
    max_sources: int = 2
    max_chars: int = 16_000


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


# ---- 端点 ----


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    kb = _get_kb()
    return kb.stats()


@app.get("/documents")
def list_documents():
    kb = _get_kb()
    docs = kb.list_docs()
    return [
        {
            "doc_id": d.doc_id,
            "source": d.source,
            "title": d.title,
            "type": d.type,
            "chunk_count": d.chunk_count,
            "ingested_at": d.ingested_at,
        }
        for d in docs
    ]


@app.post("/ingest")
def ingest(req: IngestRequest):
    kb = _get_kb()
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {req.path}")
    try:
        if p.is_dir():
            files = [
                file
                for pattern in ("*.md", "*.txt", "*.pdf", "*.docx")
                for file in sorted(p.rglob(pattern))
            ]
            results = [kb.ingest_path(str(f)) for f in files]
            return {"ingested": results}
        result = kb.ingest_path(req.path)
        return result
    except KnowledgeBaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/query")
def query(req: QueryRequest):
    kb = _get_kb()
    try:
        if req.expand:
            retrieved = kb.query_with_neighbors(
                req.question,
                top_k=req.top_k,
                neighbor_window=req.neighbor_window,
                max_sources=req.max_sources,
                max_chars=req.max_chars,
            )
        else:
            retrieved = kb.query(req.question, top_k=req.top_k)
    except EmptyStoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "expanded": req.expand,
        "chunks": [
            {
                "score": round(r.score, 4),
                "source": r.chunk.source,
                "doc_id": r.chunk.doc_id,
                "chunk_index": r.chunk.chunk_index,
                "text": r.chunk.text,
            }
            for r in retrieved
        ]
    }


@app.post("/ask")
def ask(req: AskRequest):
    kb = _get_kb()
    try:
        answer = kb.ask(req.question, top_k=req.top_k)
    except EmptyStoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "answer": answer.answer,
        "sources": [
            {
                "score": round(r.score, 4),
                "source": r.chunk.source,
                "chunk_index": r.chunk.chunk_index,
                "text": r.chunk.text,
            }
            for r in answer.sources
        ],
    }


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    kb = _get_kb()
    result = kb.delete(doc_id)
    return result


def main():
    """启动 API 服务（python -m rag.api）。"""
    import uvicorn

    host = os.getenv("KB_API_HOST", "127.0.0.1")
    port = int(os.getenv("KB_API_PORT", "8000"))
    uvicorn.run("rag.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
