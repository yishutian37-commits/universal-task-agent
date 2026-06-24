from __future__ import annotations

import array
import json
import os
import sqlite3

from rag.errors import EmbedderMismatchError
from rag.models import Chunk, Document


def _blob_to_vector(blob: bytes) -> list[float]:
    arr = array.array("f")
    arr.frombytes(blob)
    return list(arr)


def _vector_to_blob(vector: list[float]) -> bytes:
    arr = array.array("f", vector)
    return arr.tobytes()


class SqliteStore:
    """SQLite 向量存储：documents + chunks + kb_meta，向量以 float32 BLOB 存。

    建库时把 dim 写入 kb_meta，后续打开校验一致性，不一致抛
    EmbedderMismatchError。所有写入走单事务，崩溃不留半截数据。
    """

    def __init__(self, db_path: str, dim: int) -> None:
        self.db_path = db_path
        self.dim = dim
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._check_dim()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id      TEXT PRIMARY KEY,
                source      TEXT UNIQUE,
                title       TEXT,
                type        TEXT,
                chunk_count INTEGER,
                ingested_at TEXT,
                metadata    TEXT
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id    TEXT PRIMARY KEY,
                doc_id      TEXT,
                source      TEXT,
                chunk_index INTEGER,
                text        TEXT,
                metadata    TEXT,
                vector      BLOB
            );
            CREATE TABLE IF NOT EXISTS kb_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        self._conn.commit()

    def _check_dim(self) -> None:
        row = self._conn.execute(
            "SELECT value FROM kb_meta WHERE key = 'dim'"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO kb_meta (key, value) VALUES ('dim', ?)",
                (str(self.dim),),
            )
            self._conn.commit()
        elif int(row[0]) != self.dim:
            raise EmbedderMismatchError(
                f"Embedder 维度 {self.dim} 与库记录 {row[0]} 不一致，"
                "请清空库后重建（delete data/knowledge.db 后重新 ingest）"
            )

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks 和 vectors 数量不一致")
        cur = self._conn.cursor()
        try:
            for chunk, vec in zip(chunks, vectors):
                cur.execute(
                    "INSERT INTO chunks (chunk_id, doc_id, source, chunk_index, "
                    "text, metadata, vector) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk.chunk_id,
                        chunk.doc_id,
                        chunk.source,
                        chunk.chunk_index,
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        _vector_to_blob(vec),
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return len(chunks)

    def delete_by_source(self, source: str) -> int:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM chunks WHERE source = ?", (source,))
        self._conn.commit()
        return cur.rowcount

    def delete_doc(self, doc_id: str) -> int:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        deleted = cur.rowcount
        cur.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._conn.commit()
        return deleted

    def upsert_doc(self, doc: Document) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO documents (doc_id, source, title, type, chunk_count, "
            "ingested_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(doc_id) DO UPDATE SET "
            "source=excluded.source, title=excluded.title, type=excluded.type, "
            "chunk_count=excluded.chunk_count, ingested_at=excluded.ingested_at, "
            "metadata=excluded.metadata",
            (
                doc.doc_id,
                doc.source,
                doc.title,
                doc.type,
                doc.chunk_count,
                doc.ingested_at,
                json.dumps(doc.metadata, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def list_docs(self) -> list[Document]:
        rows = self._conn.execute(
            "SELECT doc_id, source, title, type, chunk_count, ingested_at, metadata "
            "FROM documents"
        ).fetchall()
        return [
            Document(
                doc_id=r[0],
                source=r[1],
                title=r[2],
                type=r[3],
                chunk_count=r[4],
                ingested_at=r[5],
                metadata=json.loads(r[6]) if r[6] else {},
            )
            for r in rows
        ]

    def all_vectors(self) -> tuple[list[list[float]], list[Chunk]]:
        rows = self._conn.execute(
            "SELECT chunk_id, doc_id, source, chunk_index, text, metadata, vector "
            "FROM chunks"
        ).fetchall()
        vectors: list[list[float]] = []
        chunks: list[Chunk] = []
        for r in rows:
            vectors.append(_blob_to_vector(r[6]))
            chunks.append(
                Chunk(
                    chunk_id=r[0],
                    doc_id=r[1],
                    source=r[2],
                    chunk_index=r[3],
                    text=r[4],
                    metadata=json.loads(r[5]) if r[5] else {},
                )
            )
        return vectors, chunks

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def clear(self) -> None:
        """清空 chunks 和 documents，保留表结构和 kb_meta（维度不变）。"""
        self._conn.execute("DELETE FROM chunks")
        self._conn.execute("DELETE FROM documents")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
