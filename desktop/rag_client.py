from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

from desktop.paths import uta_home


class RAGClient:
    """桌面应用接入 RAG 知识库的客户端。

    两种模式：
    - 内嵌模式（默认）：直接用 KnowledgeBase（HashingEmbedder + EchoGenerator），
      零外部依赖，打包后开箱即用。语义检索和 LLM 答案是临时的。
    - HTTP 模式：配置 KB_API_URL 后，通过 HTTP 调外部 RAG 服务（含真实 bge + mimo），
      获得真正的语义检索和 LLM 问答。

    模式由环境变量 KB_API_URL 决定：有值则走 HTTP，否则走内嵌。
    """

    def __init__(self, api_url: str | None = None) -> None:
        self.api_url = (api_url or os.getenv("KB_API_URL", "")).rstrip("/")
        self._kb = None

    @property
    def mode(self) -> str:
        return "http" if self.api_url else "embedded"

    def _get_embedded_kb(self):
        if self._kb is None:
            from rag.defaults import create_default_kb

            db_path = str(uta_home() / "rag" / "knowledge.db")
            self._kb = create_default_kb(db_path=db_path, use_real_models=False)
        return self._kb

    def _http(self, method: str, path: str, data: dict | None = None) -> dict[str, Any]:
        url = f"{self.api_url}{path}"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"} if body else {}
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return {"ok": False, "error": f"HTTP {exc.code}: {detail}"}
        except urllib.error.URLError as exc:
            return {"ok": False, "error": f"RAG 服务连接失败: {exc.reason}"}

    def stats(self) -> dict[str, Any]:
        if self.mode == "http":
            return self._http("GET", "/stats")
        return self._get_embedded_kb().stats()

    def list_docs(self) -> list[dict[str, Any]]:
        if self.mode == "http":
            return self._http("GET", "/documents")
        docs = self._get_embedded_kb().list_docs()
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

    def ingest(self, path: str) -> dict[str, Any]:
        if self.mode == "http":
            return self._http("POST", "/ingest", {"path": path})
        result = self._get_embedded_kb().ingest_path(path)
        return {"ok": True, **result}

    def query(self, question: str, top_k: int = 5) -> dict[str, Any]:
        if self.mode == "http":
            return self._http("POST", "/query", {"question": question, "top_k": top_k})
        from rag.errors import EmptyStoreError

        try:
            retrieved = self._get_embedded_kb().query(question, top_k=top_k)
        except EmptyStoreError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "chunks": [
                {
                    "score": round(r.score, 4),
                    "source": r.chunk.source,
                    "text": r.chunk.text[:200],
                }
                for r in retrieved
            ],
        }

    def ask(self, question: str, top_k: int = 5) -> dict[str, Any]:
        if self.mode == "http":
            return self._http("POST", "/ask", {"question": question, "top_k": top_k})
        from rag.errors import EmptyStoreError

        try:
            answer = self._get_embedded_kb().ask(question, top_k=top_k)
        except EmptyStoreError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "answer": answer.answer,
            "sources": [
                {
                    "score": round(r.score, 4),
                    "source": r.chunk.source,
                    "text": r.chunk.text[:200],
                }
                for r in answer.sources
            ],
        }

    def delete(self, target: str) -> dict[str, Any]:
        if self.mode == "http":
            return self._http("DELETE", f"/documents/{target}")
        result = self._get_embedded_kb().delete(target)
        return {"ok": True, **result}
