# RAG 知识库 v0.1-skeleton 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 RAG 知识库六层管线的骨架——目录结构、公共数据模型、统一异常、六层抽象接口、`KnowledgeBase` 编排类，全部用 fake 实现跑通空链路。

**Architecture:** 分层插件式架构（方案 3）。本阶段把六层接口契约和 `KnowledgeBase` 装配逻辑一次到位，但每层先用 fake 实现填充，确保接口可被独立测试。真实实现（TextLoader/FixedChunker/LocalEmbedder 等）留给 v0.2-mvp。

**Tech Stack:** Python 3.12、标准库 `abc`/`dataclasses`/`uuid`/`pathlib`、`pytest`。本阶段零第三方依赖（不引入 numpy/sentence-transformers/FastAPI）。

**关联 Spec:** `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`（第 3、4、5、8、9 节）

**代码风格对齐 UTA 现有代码：** `from __future__ import annotations`、`dataclass` + `field(default_factory=...)`、ABC 抽象方法、`str | None` 类型注解、模块级 docstring。

---

## 文件结构总览

本阶段创建以下文件，每个文件单一职责：

```
rag-knowledge-base/
├── rag/
│   ├── __init__.py          # 导出 KnowledgeBase（UTA 唯一入口）
│   ├── models.py            # 公共数据模型：Document/Chunk/RetrievedChunk/Answer
│   ├── errors.py            # 统一异常层级
│   ├── config.py            # 从 .env 读配置（v0.1 仅占位结构）
│   ├── kb.py                # KnowledgeBase 编排类
│   ├── loaders/base.py      # BaseLoader + LoadedDoc + LoaderFactory
│   ├── chunkers/base.py     # BaseChunker
│   ├── embeddings/base.py   # BaseEmbedder
│   ├── store/base.py        # BaseVectorStore（接口）
│   ├── retrieval/base.py    # BaseRetriever
│   └── generation/base.py   # BaseGenerator
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # 共享 fixtures：fake 组件
│   ├── test_models.py
│   ├── test_errors.py
│   ├── test_kb.py           # KnowledgeBase 编排（全 fake 组件）
│   ├── test_loaders_base.py
│   ├── test_chunkers_base.py
│   ├── test_embeddings_base.py
│   ├── test_store_base.py
│   ├── test_retrieval_base.py
│   └── test_generation_base.py
├── README.md                # 项目说明
├── requirements.txt         # v0.1 仅 pytest
├── .gitignore               # data/ 排除
└── .env.example             # 配置模板
```

---

### Task 1: 项目骨架与配置文件

**Files:**
- Create: `rag-knowledge-base/requirements.txt`
- Create: `rag-knowledge-base/.gitignore`
- Create: `rag-knowledge-base/.env.example`
- Create: `rag-knowledge-base/README.md`
- Create: `rag-knowledge-base/rag/__init__.py`（空占位，Task 8 填充导出）

- [ ] **Step 1: 创建 requirements.txt**

写入 `rag-knowledge-base/requirements.txt`：

```
pytest>=8.0.0
```

- [ ] **Step 2: 创建 .gitignore**

写入 `rag-knowledge-base/.gitignore`：

```
data/
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: 创建 .env.example**

写入 `rag-knowledge-base/.env.example`：

```
# LLM 配置（默认复用 UTA 的 mimo-v2.5-pro）
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1/chat/completions
LLM_MODEL=mimo-v2.5-pro

# Embedding 配置（provider=local 用本地模型，provider=api 调远程接口）
EMBED_PROVIDER=local
EMBED_MODEL=BAAI/bge-small-zh-v1.5
EMBED_DIM=512
EMBED_API_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1/embeddings

# 存储
KB_DB_PATH=data/knowledge.db

# API 服务
KB_API_HOST=127.0.0.1
KB_API_PORT=8000
```

- [ ] **Step 4: 创建 README.md**

写入 `rag-knowledge-base/README.md`：

```markdown
# RAG 知识库

独立 RAG 知识库系统，支持文档摄入、向量检索、LLM 问答。CLI 自用 + REST API 给 UTA 接入。

## 当前状态

- `v0.1-skeleton`：六层管线骨架（Loader/Chunker/Embedder/VectorStore/Retriever/Generator），全 fake 实现，接口契约确立。

## 架构

分层插件式，每层一个抽象接口。UTA 未来接入只需：

```python
from rag import KnowledgeBase
kb = KnowledgeBase()
answer = kb.ask("问题")
```

详细设计见 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。
```

- [ ] **Step 5: 创建包占位**

写入 `rag-knowledge-base/rag/__init__.py`（暂时空占位，Task 8 填充）：

```python
"""RAG 知识库核心库。"""
```

- [ ] **Step 6: 验证目录结构**

Run: `ls -R rag-knowledge-base/`
Expected: 看到 `rag/` 目录和四个配置文件。

- [ ] **Step 7: Commit**

```bash
git add rag-knowledge-base/
git commit -m "feat: scaffold rag knowledge base project structure"
```

---

### Task 2: 公共数据模型

**Files:**
- Create: `rag-knowledge-base/rag/models.py`
- Create: `rag-knowledge-base/tests/__init__.py`
- Create: `rag-knowledge-base/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/__init__.py`：

```python
```

写入 `rag-knowledge-base/tests/test_models.py`：

```python
from __future__ import annotations

from rag.models import Answer, Chunk, Document, RetrievedChunk


def test_document_defaults():
    doc = Document(
        doc_id="d1",
        source="notes.md",
        title="Notes",
        type="md",
        chunk_count=0,
        ingested_at="2026-06-24T00:00:00",
        metadata={},
    )
    assert doc.doc_id == "d1"
    assert doc.source == "notes.md"
    assert doc.metadata == {}


def test_chunk_has_required_fields():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    assert chunk.text == "hello"
    assert chunk.chunk_index == 0


def test_retrieved_chunk_wraps_chunk_with_score():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    rc = RetrievedChunk(chunk=chunk, score=0.9)
    assert rc.chunk.text == "hello"
    assert rc.score == 0.9


def test_answer_holds_text_and_sources():
    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        source="notes.md",
        chunk_index=0,
        text="hello",
        metadata={},
    )
    rc = RetrievedChunk(chunk=chunk, score=0.9)
    ans = Answer(answer="因为...", sources=[rc])
    assert ans.answer == "因为..."
    assert len(ans.sources) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.models'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/models.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Document:
    """摄入文档的元数据记录，对应 documents 表。"""

    doc_id: str
    source: str
    title: str
    type: str
    chunk_count: int
    ingested_at: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """切片后的文本片段。"""

    chunk_id: str
    doc_id: str
    source: str
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """检索命中的片段，附带相似度分。"""

    chunk: Chunk
    score: float


@dataclass
class Answer:
    """端到端问答结果，含答案和来源引用。"""

    answer: str
    sources: list[RetrievedChunk] = field(default_factory=list)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_models.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/models.py rag-knowledge-base/tests/
git commit -m "feat: add rag public data models"
```

---

### Task 3: 统一异常层级

**Files:**
- Create: `rag-knowledge-base/rag/errors.py`
- Create: `rag-knowledge-base/tests/test_errors.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_errors.py`：

```python
from __future__ import annotations

import pytest

from rag.errors import (
    EmbedderMismatchError,
    EmptyStoreError,
    IngestError,
    KnowledgeBaseError,
    LLMError,
    UnsupportedSourceError,
)


@pytest.mark.parametrize(
    "exc_class",
    [
        UnsupportedSourceError,
        EmbedderMismatchError,
        EmptyStoreError,
        IngestError,
        LLMError,
    ],
)
def test_all_errors_inherit_base(exc_class):
    assert issubclass(exc_class, KnowledgeBaseError)


def test_base_inherits_exception():
    assert issubclass(KnowledgeBaseError, Exception)


def test_errors_carry_message():
    err = EmptyStoreError("库里没有文档")
    assert str(err) == "库里没有文档"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.errors'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/errors.py`：

```python
"""RAG 知识库统一异常层级。快失败、明确报错、不静默吞。"""

from __future__ import annotations


class KnowledgeBaseError(Exception):
    """RAG 知识库所有异常的基类。"""


class UnsupportedSourceError(KnowledgeBaseError):
    """Loader 不支持的文件扩展名或来源类型。"""


class EmbedderMismatchError(KnowledgeBaseError):
    """Embedder 维度与已建库的维度不一致，需重建库。"""


class EmptyStoreError(KnowledgeBaseError):
    """知识库为空时执行 query/ask，需先 ingest。"""


class IngestError(KnowledgeBaseError):
    """文档摄入失败（文件读不出、切片失败、写入异常等）。"""


class LLMError(KnowledgeBaseError):
    """LLM 调用失败（超时、网络错误、响应无效等）。"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_errors.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/errors.py rag-knowledge-base/tests/test_errors.py
git commit -m "feat: add rag unified error hierarchy"
```

---

### Task 4: Loader 层接口

**Files:**
- Create: `rag-knowledge-base/rag/loaders/__init__.py`
- Create: `rag-knowledge-base/rag/loaders/base.py`
- Create: `rag-knowledge-base/tests/test_loaders_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_loaders_base.py`：

```python
from __future__ import annotations

import pytest

from rag.errors import UnsupportedSourceError
from rag.loaders.base import LoadedDoc, LoaderFactory


def test_loaded_doc_holds_text_and_source():
    doc = LoadedDoc(text="内容", source="a.md", metadata={"type": "md"})
    assert doc.text == "内容"
    assert doc.source == "a.md"


class _FakeMdLoader:
    def load(self, source: str) -> LoadedDoc:
        return LoadedDoc(text="fake", source=source, metadata={"type": "md"})


def test_factory_routes_by_extension():
    factory = LoaderFactory({".md": _FakeMdLoader()})
    loader = factory.get("notes.md")
    doc = loader.load("notes.md")
    assert doc.metadata["type"] == "md"


def test_factory_raises_on_unsupported():
    factory = LoaderFactory({".md": _FakeMdLoader()})
    with pytest.raises(UnsupportedSourceError):
        factory.get("unknown.xyz")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_loaders_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.loaders'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/loaders/__init__.py`：

```python
"""文档摄入层。"""
```

写入 `rag-knowledge-base/rag/loaders/base.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_loaders_base.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/loaders/ rag-knowledge-base/tests/test_loaders_base.py
git commit -m "feat: add loader base interface and factory"
```

---

### Task 5: Chunker 层接口

**Files:**
- Create: `rag-knowledge-base/rag/chunkers/__init__.py`
- Create: `rag-knowledge-base/rag/chunkers/base.py`
- Create: `rag-knowledge-base/tests/test_chunkers_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_chunkers_base.py`：

```python
from __future__ import annotations

from rag.chunkers.base import BaseChunker
from rag.models import Chunk


class _DoubleChunker(BaseChunker):
    """fake：把文本按 2 字符切片，无重叠。"""

    def chunk_text(self, text: str, doc_id: str, source: str) -> list[Chunk]:
        pieces = [text[i : i + 2] for i in range(0, len(text), 2)]
        return [
            Chunk(
                chunk_id=f"{doc_id}-{i}",
                doc_id=doc_id,
                source=source,
                chunk_index=i,
                text=p,
                metadata={},
            )
            for i, p in enumerate(pieces)
        ]


def test_chunker_returns_chunks():
    chunker = _DoubleChunker()
    chunks = chunker.chunk_text("abcdef", "d1", "a.md")
    assert len(chunks) == 3
    assert chunks[0].text == "ab"
    assert chunks[2].chunk_index == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_chunkers_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.chunkers'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/chunkers/__init__.py`：

```python
"""文本切片层。"""
```

写入 `rag-knowledge-base/rag/chunkers/base.py`：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk


class BaseChunker(ABC):
    """文本切片接口。把纯文本切成带索引的 Chunk 列表。"""

    @abstractmethod
    def chunk_text(
        self, text: str, doc_id: str, source: str
    ) -> list[Chunk]:
        """把文本切片，返回带 chunk_id/doc_id/chunk_index 的片段列表。"""
```

> **注意：** 这里接口命名为 `chunk_text`（输入纯文本 + doc_id + source）而非 spec 里的 `chunk(doc)`，因为编排时 Loader 已产出纯文本、`KnowledgeBase` 会先生成 `doc_id` 再调切片。`chunk_text` 更贴合实际调用链，避免 Chunker 依赖 `LoadedDoc` 造成跨层耦合。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_chunkers_base.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/chunkers/ rag-knowledge-base/tests/test_chunkers_base.py
git commit -m "feat: add chunker base interface"
```

---

### Task 6: Embedder 层接口

**Files:**
- Create: `rag-knowledge-base/rag/embeddings/__init__.py`
- Create: `rag-knowledge-base/rag/embeddings/base.py`
- Create: `rag-knowledge-base/tests/test_embeddings_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_embeddings_base.py`：

```python
from __future__ import annotations

from rag.embeddings.base import BaseEmbedder


class _FakeEmbedder(BaseEmbedder):
    """fake：把每个字符的 ord 编码成定长向量。"""

    @property
    def dim(self) -> int:
        return 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(ord(c)) for c in t[: self.dim]] + [0.0] * (self.dim - len(t)) for t in texts]


def test_embedder_returns_equal_length():
    emb = _FakeEmbedder()
    vectors = emb.embed(["ab", "c"])
    assert len(vectors) == 2
    assert all(len(v) == emb.dim for v in vectors)


def test_embedder_dim_is_constant():
    emb = _FakeEmbedder()
    assert emb.dim == 4
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_embeddings_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.embeddings'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/embeddings/__init__.py`：

```python
"""嵌入向量层。"""
```

写入 `rag-knowledge-base/rag/embeddings/base.py`：

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """嵌入接口。把文本批量转成向量。dim 是契约——建库后不可变。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度，建库时锁定。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，返回与输入等长的向量列表。"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_embeddings_base.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/embeddings/ rag-knowledge-base/tests/test_embeddings_base.py
git commit -m "feat: add embedder base interface"
```

---

### Task 7: VectorStore 层接口

**Files:**
- Create: `rag-knowledge-base/rag/store/__init__.py`
- Create: `rag-knowledge-base/rag/store/base.py`
- Create: `rag-knowledge-base/tests/test_store_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_store_base.py`：

```python
from __future__ import annotations

from rag.models import Chunk, Document
from rag.store.base import BaseVectorStore


class _FakeStore(BaseVectorStore):
    """fake：全部用内存字典存。"""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []
        self.docs: dict[str, Document] = {}

    def add(self, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def delete_by_source(self, source):
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.source != source]
        return before - len(self.chunks)

    def delete_doc(self, doc_id):
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        self.docs.pop(doc_id, None)
        return before - len(self.chunks)

    def upsert_doc(self, doc):
        self.docs[doc.doc_id] = doc

    def list_docs(self):
        return list(self.docs.values())

    def all_vectors(self):
        return self.vectors, self.chunks

    def count(self):
        return len(self.chunks)


def _make_chunk(source="a.md", doc_id="d1"):
    return Chunk(
        chunk_id="c1", doc_id=doc_id, source=source,
        chunk_index=0, text="t", metadata={},
    )


def test_add_and_count():
    store = _FakeStore()
    n = store.add([_make_chunk()], [[1.0, 2.0]])
    assert n == 1
    assert store.count() == 1


def test_delete_by_source():
    store = _FakeStore()
    store.add([_make_chunk()], [[1.0, 2.0]])
    assert store.delete_by_source("a.md") == 1
    assert store.count() == 0


def test_delete_doc():
    store = _FakeStore()
    store.add([_make_chunk(doc_id="d1")], [[1.0]])
    assert store.delete_doc("d1") == 1
    assert store.count() == 0


def test_list_docs():
    store = _FakeStore()
    doc = Document("d1", "a.md", "A", "md", 1, "2026", {})
    store.upsert_doc(doc)
    assert len(store.list_docs()) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_store_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.store'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/store/__init__.py`：

```python
"""向量存储层。"""
```

写入 `rag-knowledge-base/rag/store/base.py`：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk, Document


class BaseVectorStore(ABC):
    """向量存储接口。管理 chunks、向量和文档元数据，支持幂等去重。"""

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """写入切片和对应向量，返回写入条数。"""

    @abstractmethod
    def delete_by_source(self, source: str) -> int:
        """按来源删除所有 chunk（幂等摄入用），返回删除条数。"""

    @abstractmethod
    def delete_doc(self, doc_id: str) -> int:
        """按 doc_id 删除文档及其 chunk，返回删除条数。"""

    @abstractmethod
    def upsert_doc(self, doc: Document) -> None:
        """写入或更新文档元数据。"""

    @abstractmethod
    def list_docs(self) -> list[Document]:
        """列出库内所有文档。"""

    @abstractmethod
    def all_vectors(self) -> tuple[list[list[float]], list[Chunk]]:
        """返回全部向量和对应 chunk，供检索层批量读取。"""

    @abstractmethod
    def count(self) -> int:
        """返回库内 chunk 总数。"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_store_base.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/store/ rag-knowledge-base/tests/test_store_base.py
git commit -m "feat: add vector store base interface"
```

---

### Task 8: Retriever 层接口

**Files:**
- Create: `rag-knowledge-base/rag/retrieval/__init__.py`
- Create: `rag-knowledge-base/rag/retrieval/base.py`
- Create: `rag-knowledge-base/tests/test_retrieval_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_retrieval_base.py`：

```python
from __future__ import annotations

from rag.models import Chunk, RetrievedChunk
from rag.retrieval.base import BaseRetriever


class _FakeRetriever(BaseRetriever):
    """fake：按向量第一维大小排序，取 top-k。"""

    def search(self, vectors, chunks, query_vec, top_k):
        scored = [
            RetrievedChunk(chunk=c, score=query_vec[0] + v[0])
            for v, c in zip(vectors, chunks)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]


def test_search_returns_top_k_sorted():
    retriever = _FakeRetriever()
    chunks = [
        Chunk(f"c{i}", "d", "s", i, f"t{i}", {}) for i in range(3)
    ]
    vectors = [[0.1], [0.9], [0.5]]
    results = retriever.search(vectors, chunks, [1.0], top_k=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert results[0].chunk.text == "t1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_retrieval_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.retrieval'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/retrieval/__init__.py`：

```python
"""检索层。"""
```

写入 `rag-knowledge-base/rag/retrieval/base.py`：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk, RetrievedChunk


class BaseRetriever(ABC):
    """检索接口。输入查询向量 + 全量向量，返回带分的 top-k 片段。"""

    @abstractmethod
    def search(
        self,
        vectors: list[list[float]],
        chunks: list[Chunk],
        query_vec: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """在给定向量集中检索，返回按相似度排序的 top-k 结果。"""
```

> **注意：** 检索接口签名是 `search(vectors, chunks, query_vec, top_k)`，由 `KnowledgeBase` 从 store 读出全量后传入，而不是 Retriever 自己持有 store 引用。这样 Retriever 是无状态的纯函数式组件，更容易测试和替换（未来 BM25/混合检索实现时换实现不动上层）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_retrieval_base.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/retrieval/ rag-knowledge-base/tests/test_retrieval_base.py
git commit -m "feat: add retriever base interface"
```

---

### Task 9: Generator 层接口

**Files:**
- Create: `rag-knowledge-base/rag/generation/__init__.py`
- Create: `rag-knowledge-base/rag/generation/base.py`
- Create: `rag-knowledge-base/tests/test_generation_base.py`

- [ ] **Step 1: 写失败测试**

写入 `rag-knowledge-base/tests/test_generation_base.py`：

```python
from __future__ import annotations

from rag.generation.base import BaseGenerator
from rag.models import Chunk


class _FakeGenerator(BaseGenerator):
    def generate(self, question, contexts):
        refs = ", ".join(c.source for c in contexts)
        return f"关于「{question}」的回答，来源：{refs}"


def test_generate_uses_contexts():
    gen = _FakeGenerator()
    chunks = [
        Chunk("c1", "d1", "a.md", 0, "内容A", {}),
        Chunk("c2", "d1", "b.md", 0, "内容B", {}),
    ]
    answer = gen.generate("什么是X", chunks)
    assert "a.md" in answer
    assert "b.md" in answer
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_generation_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.generation'`

- [ ] **Step 3: 写实现**

写入 `rag-knowledge-base/rag/generation/__init__.py`：

```python
"""答案生成层。"""
```

写入 `rag-knowledge-base/rag/generation/base.py`：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.models import Chunk


class BaseGenerator(ABC):
    """答案生成接口。基于检索片段和问题，生成带引用的答案。"""

    @abstractmethod
    def generate(self, question: str, contexts: list[Chunk]) -> str:
        """根据问题上下文片段生成答案文本。"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_generation_base.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add rag-knowledge-base/rag/generation/ rag-knowledge-base/tests/test_generation_base.py
git commit -m "feat: add generator base interface"
```

---

### Task 10: KnowledgeBase 编排类

**Files:**
- Create: `rag-knowledge-base/rag/kb.py`
- Create: `rag-knowledge-base/tests/conftest.py`
- Create: `rag-knowledge-base/tests/test_kb.py`

这是本阶段核心——把六层 fake 组件装配起来，跑通 ingest/query/ask 的编排逻辑（含空库校验、幂等去重编排）。

- [ ] **Step 1: 写共享 fixtures**

写入 `rag-knowledge-base/tests/conftest.py`：

```python
from __future__ import annotations

import uuid

import pytest

from rag.chunkers.base import BaseChunker
from rag.embeddings.base import BaseEmbedder
from rag.generation.base import BaseGenerator
from rag.loaders.base import BaseLoader, LoadedDoc, LoaderFactory
from rag.models import Chunk
from rag.retrieval.base import BaseRetriever
from rag.store.base import BaseVectorStore
from rag.models import Document


class FakeLoader(BaseLoader):
    def __init__(self, text: str = "示例文本内容") -> None:
        self._text = text

    def load(self, source: str) -> LoadedDoc:
        return LoadedDoc(text=self._text, source=source, metadata={"type": "md"})


class FakeChunker(BaseChunker):
    def chunk_text(self, text, doc_id, source):
        # 简单按句号切
        pieces = [p for p in text.split("。") if p]
        if not pieces:
            pieces = [text]
        return [
            Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                source=source,
                chunk_index=i,
                text=p,
                metadata={},
            )
            for i, p in enumerate(pieces)
        ]


class FakeEmbedder(BaseEmbedder):
    @property
    def dim(self) -> int:
        return 3

    def embed(self, texts):
        return [[float(len(t) % 10), float(i), 0.0] for i, t in enumerate(texts)]


class FakeStore(BaseVectorStore):
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []
        self.docs: dict[str, Document] = {}

    def add(self, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def delete_by_source(self, source):
        before = len(self.chunks)
        keep = [(v, c) for v, c in zip(self.vectors, self.chunks) if c.source != source]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        return before - len(self.chunks)

    def delete_doc(self, doc_id):
        before = len(self.chunks)
        keep = [(v, c) for v, c in zip(self.vectors, self.chunks) if c.doc_id != doc_id]
        self.vectors = [v for v, _ in keep]
        self.chunks = [c for _, c in keep]
        self.docs.pop(doc_id, None)
        return before - len(self.chunks)

    def upsert_doc(self, doc):
        self.docs[doc.doc_id] = doc

    def list_docs(self):
        return list(self.docs.values())

    def all_vectors(self):
        return self.vectors, self.chunks

    def count(self):
        return len(self.chunks)


class FakeRetriever(BaseRetriever):
    def search(self, vectors, chunks, query_vec, top_k):
        scored = [
            (sum((a - b) ** 2 for a, b in zip(v, query_vec)), c)
            for v, c in zip(vectors, chunks)
        ]
        scored.sort(key=lambda x: x[0])  # 距离越小越相似
        from rag.models import RetrievedChunk

        return [RetrievedChunk(chunk=c, score=-d) for d, c in scored[:top_k]]


class FakeGenerator(BaseGenerator):
    def generate(self, question, contexts):
        refs = ", ".join(c.source for c in contexts)
        return f"答案（来源 {refs}）：关于「{question}」"


@pytest.fixture
def fake_components():
    """返回一组 fake 组件，供 KnowledgeBase 装配测试。"""
    store = FakeStore()
    return {
        "loader_factory": LoaderFactory({".md": FakeLoader("第一句。第二句。第三句。")}),
        "chunker": FakeChunker(),
        "embedder": FakeEmbedder(),
        "store": store,
        "retriever": FakeRetriever(),
        "generator": FakeGenerator(),
    }
```

- [ ] **Step 2: 写失败测试**

写入 `rag-knowledge-base/tests/test_kb.py`：

```python
from __future__ import annotations

import pytest

from rag.errors import EmptyStoreError
from rag.kb import KnowledgeBase


def test_ask_on_empty_store_raises(fake_components):
    kb = KnowledgeBase(**fake_components)
    with pytest.raises(EmptyStoreError):
        kb.ask("任何问题")


def test_query_on_empty_store_raises(fake_components):
    kb = KnowledgeBase(**fake_components)
    with pytest.raises(EmptyStoreError):
        kb.query("任何问题")


def test_ingest_then_ask_roundtrip(fake_components):
    kb = KnowledgeBase(**fake_components)
    result = kb.ingest_path("notes.md")
    assert result["chunk_count"] > 0
    assert result["source"] == "notes.md"

    answer = kb.ask("问题")
    assert "notes.md" in answer.answer
    assert len(answer.sources) > 0


def test_ingest_is_idempotent(fake_components):
    kb = KnowledgeBase(**fake_components)
    kb.ingest_path("notes.md")
    first_count = kb._store.count()

    kb.ingest_path("notes.md")  # 重复摄入
    second_count = kb._store.count()

    assert second_count == first_count  # 不应翻倍


def test_query_returns_chunks_without_llm(fake_components):
    kb = KnowledgeBase(**fake_components)
    kb.ingest_path("notes.md")
    chunks = kb.query("问题", top_k=2)
    assert len(chunks) <= 2
    assert all(hasattr(c, "score") for c in chunks)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd rag-knowledge-base && python -m pytest tests/test_kb.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.kb'`

- [ ] **Step 4: 写实现**

写入 `rag-knowledge-base/rag/kb.py`：

```python
from __future__ import annotations

import os
import uuid
from datetime import datetime

from rag.chunkers.base import BaseChunker
from rag.embeddings.base import BaseEmbedder
from rag.errors import EmptyStoreError
from rag.generation.base import BaseGenerator
from rag.loaders.base import LoaderFactory
from rag.models import Answer, Document, RetrievedChunk
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
    ) -> None:
        self.loader_factory = loader_factory
        self.chunker = chunker
        self.embedder = embedder
        self._store = store
        self.retriever = retriever
        self.generator = generator

    def ingest_path(self, source: str) -> dict:
        """摄入单个来源（文件路径）：加载→切片→嵌入→存储，幂等。"""
        loader = self.loader_factory.get(source)
        loaded = loader.load(source)

        doc_id = str(uuid.uuid4())
        # 幂等：先删旧的同源 chunk
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

        query_vec = self.embedder.embed([question])[0]
        vectors, chunks = self._store.all_vectors()
        if not chunks:
            raise EmptyStoreError("知识库为空，请先 ingest 文档")
        return self.retriever.search(vectors, chunks, query_vec, top_k)

    def ask(self, question: str, top_k: int = 5) -> Answer:
        """端到端问答：检索 → 生成，返回带来源引用的答案。"""
        retrieved = self.query(question, top_k=top_k)
        contexts = [r.chunk for r in retrieved]
        answer_text = self.generator.generate(question, contexts)
        return Answer(answer=answer_text, sources=retrieved)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd rag-knowledge-base && python -m pytest tests/test_kb.py -v`
Expected: PASS（5 passed）

- [ ] **Step 6: Commit**

```bash
git add rag-knowledge-base/rag/kb.py rag-knowledge-base/tests/conftest.py rag-knowledge-base/tests/test_kb.py
git commit -m "feat: add knowledgebase orchestrator with fake components"
```

---

### Task 11: 包导出与全量测试

**Files:**
- Modify: `rag-knowledge-base/rag/__init__.py`

- [ ] **Step 1: 填充包导出**

覆盖写入 `rag-knowledge-base/rag/__init__.py`：

```python
"""RAG 知识库核心库。

UTA 未来接入的唯一入口：

    from rag import KnowledgeBase
    kb = KnowledgeBase()
    answer = kb.ask("问题")
"""

from __future__ import annotations

from rag.kb import KnowledgeBase
from rag.models import Answer, Chunk, Document, RetrievedChunk

__all__ = ["KnowledgeBase", "Answer", "Chunk", "Document", "RetrievedChunk"]
```

- [ ] **Step 2: 写导出测试**

追加到 `rag-knowledge-base/tests/test_models.py` 末尾（或在 test_kb.py 新增）。这里单独建 `tests/test_package.py`：

写入 `rag-knowledge-base/tests/test_package.py`：

```python
from __future__ import annotations

import rag


def test_knowledgebase_exported():
    assert hasattr(rag, "KnowledgeBase")


def test_models_exported():
    for name in ["Answer", "Chunk", "Document", "RetrievedChunk"]:
        assert hasattr(rag, name)


def test_all_list_consistent():
    for name in rag.__all__:
        assert hasattr(rag, name)
```

- [ ] **Step 3: 运行全量测试**

Run: `cd rag-knowledge-base && python -m pytest -v`
Expected: 全部 PASS（约 30+ passed，覆盖所有层 + 包导出）

- [ ] **Step 4: Commit**

```bash
git add rag-knowledge-base/rag/__init__.py rag-knowledge-base/tests/test_package.py
git commit -m "feat: export knowledgebase as rag package entrypoint"
```

---

### Task 12: 阶段收尾——README 更新与验收

**Files:**
- Modify: `rag-knowledge-base/README.md`

- [ ] **Step 1: 更新 README 加验收说明**

在 `rag-knowledge-base/README.md` 的"当前状态"部分后追加：

```markdown
## v0.1 验收

```bash
cd rag-knowledge-base
python -m pip install -r requirements.txt
python -m pytest -v
```

预期：六层接口 + KnowledgeBase 编排测试全部通过。本阶段为骨架，真实 Loader/Embedder/Store 实现见 v0.2-mvp。
```

- [ ] **Step 2: 最终全量验证**

Run: `cd rag-knowledge-base && python -m pytest -v`
Expected: 全绿

Run: `cd rag-knowledge-base && python -c "from rag import KnowledgeBase; print(KnowledgeBase)"`
Expected: 打印 `<class 'rag.kb.KnowledgeBase'>`，无导入错误

- [ ] **Step 3: Commit**

```bash
git add rag-knowledge-base/README.md
git commit -m "docs: add v0.1 skeleton acceptance section"
```

---

## 自检结果

**1. Spec 覆盖（针对 v0.1-skeleton 阶段）：**
- ✅ 项目布局（spec §3）→ Task 1
- ✅ 公共数据模型 Document/Chunk/RetrievedChunk/Answer（spec §5）→ Task 2
- ✅ 统一异常层级（spec §8）→ Task 3
- ✅ 六层接口契约（spec §5）→ Task 4-9
- ✅ KnowledgeBase 编排（spec §4）→ Task 10
- ✅ UTA 唯一接入面导出（spec §3）→ Task 11
- ✅ 测试策略——每层独立单测 + fake 组件（spec §9）→ Task 2-11 各层测试 + Task 10 conftest

**2. 占位符扫描：** 无 TBD/TODO，所有 step 含完整代码和确切命令。

**3. 类型一致性：**
- `Chunk` 字段（chunk_id/doc_id/source/chunk_index/text/metadata）在 models、loaders、chunkers、store 测试中一致 ✅
- `BaseRetriever.search(vectors, chunks, query_vec, top_k)` 与 `KnowledgeBase.query` 调用点一致 ✅
- `BaseChunker.chunk_text(text, doc_id, source)` 与 `KnowledgeBase.ingest_path` 调用点一致 ✅
- `BaseVectorStore` 七个方法在接口、fake 实现、`KnowledgeBase` 调用点一致 ✅

**未覆盖（留给后续阶段，符合预期）：**
- 真实 Loader（TextLoader/PdfLoader）→ v0.2 / v0.5
- FixedChunker / LocalEmbedder / ApiEmbedder → v0.2
- SqliteStore 真实实现 → v0.2
- VectorRetriever（numpy 余弦）→ v0.2
- LLMGenerator（mimo 调用）→ v0.2
- CLI / FastAPI → v0.3 / v0.4
