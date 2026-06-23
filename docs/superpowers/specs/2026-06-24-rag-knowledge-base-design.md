# RAG 知识库 · 设计文档

- **日期**：2026-06-24
- **状态**：已设计，待评审
- **关联项目**：UTA (Universal Task Agent)，当前 v1.0

## 1. 目标与定位

构建一个**独立的 RAG 知识库系统**，能单独运行（CLI + REST API），并在架构上为**后期接入 UTA** 留出干净接口。UTA 未来接入时只需调用 `KnowledgeBase` 一个类，不耦合 RAG 内部实现。

### 核心诉求

| 维度 | 决策 |
|------|------|
| 定位 | 独立 RAG 知识库，为后期接入 UTA 留干净接口 |
| 内容 | 通用文档（PDF/Word/MD/网页）+ 个人笔记/UTA 记忆 + 结构化数据（表格/JSON） |
| 形态 | CLI（自用）+ REST API（给 UTA 留接口），不做 Web |
| Embedding | 抽象 `Embedder` 接口，默认本地（sentence-transformers/bge），可切 API |
| 向量库 | SQLite 存向量 + numpy 余弦相似度 |
| LLM | 复用 mimo-v2.5-pro，抽象 `LLMProvider`/`Generator`，配置在 `.env` |

### 内容范围

三类内容共用一套 RAG 管线，仅切片/检索策略略有不同，**不拆成子项目**：

- **A. 通用文档问答** —— PDF / Word / Markdown / 网页，检索片段 + LLM 生成答案。
- **C. 个人/团队笔记知识库** —— 笔记、会议纪要、经验沉淀（含 UTA 的 `memory/*.json`）。
- **D. 结构化数据问答** —— 文档 + 半结构化数据（表格、JSON）混合检索。

## 2. 架构方案选择

在三个候选方案中选定 **方案 3：分层插件式架构**。

| 方案 | 描述 | 结论 |
|------|------|------|
| 方案 1 Lean MVP | 最小管线一口气打通，接口先具体后抽象 | ❌ 接 UTA 时返工 |
| 方案 2 全功能 | v1 即做混合检索、重排、全格式 | ❌ 违背 YAGNI，周期长 |
| **方案 3 分层插件式** | 一次定义六层抽象，每层 v1 只实现最简版本 | ✅ **选定** |

**选定理由**：诉求本质就是要求分层抽象（可插拔 Embedder、可配置 LLM、为接 UTA 留口）。方案 3 把抽象做对，但每层先实现最简版，避免过度设计。每层能独立单测，换实现不动别的层，UTA 未来接入只需调 `KnowledgeBase` 一个接口。

## 3. 项目布局与分层架构

```
rag-knowledge-base/
├── README.md
├── requirements.txt                 # 独立依赖（不污染 UTA）
├── .env.example                     # LLM / Embedding 配置
├── rag/                             # 核心库（分层管线）
│   ├── __init__.py                  # 暴露 KnowledgeBase（UTA 未来唯一入口）
│   ├── kb.py                        # KnowledgeBase 编排类
│   ├── config.py                    # 从 .env 读配置
│   ├── models.py                    # 公共数据模型
│   ├── errors.py                    # 统一异常层级
│   ├── loaders/                     # 第1层：文档摄入
│   │   ├── base.py                  #   Loader 接口
│   │   ├── text_loader.py           #   TXT/MD（v1 实现）
│   │   ├── pdf_loader.py            #   （后续阶段）
│   │   └── docx_loader.py           #   （后续阶段）
│   ├── chunkers/                    # 第2层：切片
│   │   ├── base.py                  #   Chunker 接口
│   │   └── fixed_chunker.py         #   定长+重叠（v1 实现）
│   ├── embeddings/                  # 第3层：嵌入
│   │   ├── base.py                  #   Embedder 接口
│   │   ├── local_embedder.py        #   sentence-transformers（默认）
│   │   └── api_embedder.py          #   OpenAI 兼容 API
│   ├── store/                       # 第4层：存储
│   │   └── sqlite_store.py          #   SQLite + 元数据 + 向量
│   ├── retrieval/                   # 第5层：检索
│   │   ├── base.py                  #   Retriever 接口
│   │   └── vector_retriever.py      #   numpy 余弦（v1 实现）
│   └── generation/                  # 第6层：生成
│       ├── base.py                  #   Generator 接口
│       └── llm_generator.py         #   mimo-v2.5-pro（默认）
├── cli.py                           # CLI 入口（自用）
├── api.py                           # REST API 入口（给 UTA）
├── data/                            # SQLite 文件、原始文档（gitignore）
└── tests/                           # 每层独立单测（对齐 UTA 风格）
```

### 关键设计点

1. **UTA 接入面只有 `KnowledgeBase` 一个类**（`rag/__init__.py` 导出）：

   ```python
   from rag import KnowledgeBase
   kb = KnowledgeBase()
   answer = kb.ask("这段经验是什么意思？")          # 端到端问答
   chunks = kb.query("类似的经验")                  # 只要检索片段
   kb.ingest_path("./memory/lessons.json")         # 摄入文档
   ```

2. **六层管线，每层一个抽象接口 + 一个 v1 实现**。每层能独立单测，换实现不动别的层。

3. **CLI 和 API 都是 `KnowledgeBase` 的薄壳**：CLI 负责参数解析，API 负责 HTTP 序列化，都不含业务逻辑。保证两个入口行为一致。

4. **独立依赖**：`rag-knowledge-base/requirements.txt` 独立管理，不写进 UTA 的 `requirements.txt`，UTA 不引入 RAG 也能跑；未来 UTA 想用，再在自己的依赖里加一行。

## 4. 数据流与管线

### 摄入流（ingest）

```
文档文件 (MD/TXT/...)
   │
   ▼
[Loader]      按扩展名路由 → 提取纯文本 + 元数据(source, title, ingested_at)
   │
   ▼
[Chunker]     定长切片(默认512 token) + 重叠(默认64 token)，保留 chunk_index
   │
   ▼
[Embedder]    批量嵌入每个 chunk → (chunk_id, vector)
   │
   ▼
[VectorStore] 写入 SQLite: chunks 表存文本/元数据, 向量以 BLOB 存
   │
   ▼
返回 ingest 结果 {doc_id, chunk_count, source}
```

**幂等性**：摄入按 `source`（文件路径或 URL）去重——同一文件重复 ingest 先删旧 chunk 再写新，避免重复向量。可反复 ingest 整个目录而不膨胀。

### 问答流（ask）

```
用户提问
   │
   ▼
[Embedder]    同一个 Embedder 把问题转成查询向量
   │
   ▼
[Retriever]   向量检索 top-k(默认5) chunk + 拼元数据
   │
   ▼
[Generator]   组装 prompt = 系统指令 + 检索片段 + 问题
              → 调 mimo-v2.5-pro 生成答案，附引用来源
   │
   ▼
返回 {answer, sources: [{source, chunk_index, text}]}
```

### 两个检索入口

- **`query(question)`** —— 只检索返回原始片段（给 UTA 这种需要自己组装 prompt 的调用方用）。
- **`ask(question)`** —— 端到端走完含 LLM 生成。始终带 `sources` 来源引用，RAG 可追溯。

### 管线编排：`KnowledgeBase` 类

```python
class KnowledgeBase:
    def __init__(self, config=None):
        # 按配置组装六层组件（默认装配 v1 实现）
        self.loader_factory = ...      # 按扩展名选 Loader
        self.chunker = FixedChunker(...)
        self.embedder = LocalEmbedder(...)   # 或 ApiEmbedder
        self.store = SqliteStore(...)
        self.retriever = VectorRetriever(...)
        self.generator = LLMGenerator(...)

    def ingest_path(self, path) -> dict: ...      # 摄入单文件/目录
    def query(self, question, top_k=5) -> list[RetrievedChunk]: ...   # 只检索
    def ask(self, question, top_k=5) -> Answer: ...                   # 端到端
```

`KnowledgeBase` 是**唯一知道全部六层**的类，其它每层只依赖相邻层的接口。

## 5. 六层接口契约

### 公共数据模型（`rag/models.py`）

```python
@dataclass
class Document:
    doc_id: str            # uuid
    source: str            # 原始路径/URL（去重 key）
    title: str
    type: str              # md/txt/pdf/docx/url
    chunk_count: int
    ingested_at: str       # ISO 时间戳
    metadata: dict

@dataclass
class Chunk:
    chunk_id: str          # uuid
    doc_id: str            # 所属文档
    source: str            # 原始路径/URL（去重 key）
    chunk_index: int       # 文档内序号
    text: str
    metadata: dict         # title, ingested_at, 页码等

@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float           # 相似度分

@dataclass
class Answer:
    answer: str
    sources: list[RetrievedChunk]
```

### 第 1 层 · Loader

```python
class BaseLoader(ABC):
    @abstractmethod
    def load(self, source: str) -> LoadedDoc:
        """source = 文件路径或 URL；返回纯文本 + 基础元数据"""

@dataclass
class LoadedDoc:
    text: str
    source: str
    metadata: dict         # {title, type, page_count...}
```

`LoaderFactory` 按扩展名/MIME 路由：`.md/.txt → TextLoader`（v1），`.pdf → PdfLoader`（后续）。**未识别类型抛 `UnsupportedSourceError`，不静默跳过。**

### 第 2 层 · Chunker

```python
class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, doc: LoadedDoc) -> list[Chunk]:
        """纯文本 → 切片列表，赋予 chunk_id/doc_id/chunk_index"""
```

`FixedChunker`：按 token 数（默认 512）切，重叠 64 token。短文档（< chunk_size）整体作为一个 chunk，不丢弃。

### 第 3 层 · Embedder

```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，返回与输入等长的向量列表"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度（建库时必须确定）"""
```

- `LocalEmbedder`：`sentence-transformers`，默认模型 `BAAI/bge-small-zh-v1.5`（中文好、512 维、轻量）。
- `ApiEmbedder`：OpenAI 兼容 `/v1/embeddings`。
- **`dim` 是契约的一部分**——建库后维度不可变，换 Embedder 必须重建库（启动时校验，不一致直接报错）。

### 第 4 层 · VectorStore

```python
class VectorStore:
    def __init__(self, db_path: str, dim: int): ...
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int: ...  # 返回写入数
    def delete_by_source(self, source: str) -> int: ...     # 幂等去重用
    def delete_doc(self, doc_id: str) -> int: ...           # 手动删某文档
    def list_docs(self) -> list[Document]: ...              # CLI 列出库里有什么
    def all_vectors(self) -> tuple[np.ndarray, list[Chunk]]: ...  # 给检索层批量读
    def count(self) -> int: ...
```

### 第 5 层 · Retriever

```python
class BaseRetriever(ABC):
    @abstractmethod
    def search(self, query_vec: list[float], top_k: int) -> list[RetrievedChunk]:
        """输入查询向量，返回带分的 top-k 片段"""
```

`VectorRetriever`：一次性读全部向量进 numpy，余弦相似度排序。**接口保留给后续 BM25/混合检索扩展。**

### 第 6 层 · Generator

```python
class BaseGenerator(ABC):
    @abstractmethod
    def generate(self, question: str, contexts: list[Chunk]) -> str:
        """基于检索片段生成答案"""
```

`LLMGenerator`：组装 prompt（系统指令 + 编号片段 + 问题），调 mimo-v2.5-pro，要求答案标注 `[1][2]` 引用编号。

### 各层依赖关系（严格单向）

```
Loader ──► Chunker ──► Embedder ──┐
                                   ├─► VectorStore ──► Retriever ──► Generator
              query 向量 ──────────┘
```

每层只依赖相邻层的数据类型，不跨层依赖具体实现类。

## 6. 存储结构与 SQLite Schema

### 表结构

```sql
-- 文档元数据（幂等去重的核心）
CREATE TABLE documents (
    doc_id      TEXT PRIMARY KEY,      -- uuid
    source      TEXT UNIQUE,           -- 路径/URL，去重 key
    title       TEXT,
    type        TEXT,                  -- md/txt/pdf/docx/url
    chunk_count INTEGER,
    ingested_at TEXT,                  -- ISO 时间戳
    metadata    TEXT                   -- JSON
);

-- 切片 + 向量
CREATE TABLE chunks (
    chunk_id    TEXT PRIMARY KEY,      -- uuid
    doc_id      TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
    source      TEXT,                  -- 冗余存，方便直接按 source 过滤
    chunk_index INTEGER,
    text        TEXT,
    metadata    TEXT,                  -- JSON
    vector      BLOB                   -- float32 连续字节
);

-- 维度记录（建库时锁定，换 Embedder 时校验）
CREATE TABLE kb_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- 固定行：dim=512, embedder=bge-small-zh-v1.5, created_at=...
```

### 关键设计决策

1. **向量存 BLOB 而非 JSON** —— 512 维 × 4 字节 = 2KB/向量，比 JSON 字符串小 3-4 倍，numpy 可 `np.frombuffer()` 零拷贝读取。

   ```python
   # 写：vector.astype(np.float32).tobytes()
   # 读：np.frombuffer(blob, dtype=np.float32)
   ```

2. **维度锁定（`kb_meta` 表）** —— 启动时校验 `kb_meta.dim == 当前 Embedder.dim`，不一致直接报错并提示重建库。

3. **幂等摄入靠 `source` 唯一约束** —— 整个去重在单事务里完成（DELETE 旧 chunks + DELETE documents，再重写），中途崩溃不留半截数据。

4. **全量读进内存做检索** —— 千级向量一次性 `SELECT` 进 numpy 矩阵是毫秒级。`VectorRetriever` 启动时加载一次，新增摄入后重新加载。接口不暴露此细节。

### 文件布局

```
rag-knowledge-base/data/
├── knowledge.db          # 上述 SQLite 库
└── uploads/              # ingest 进来的原始文档副本（可选保留，便于重建）
```

`data/` 整个进 `.gitignore`。

## 7. CLI 与 REST API 接口

两个入口都是 `KnowledgeBase` 的薄壳，共享同一套行为。

### CLI（`cli.py`，argparse，对齐 UTA 风格）

```bash
# 摄入：文件或目录，递归
python cli.py ingest <path> [--recursive]
python cli.py ingest ./notes.md
python cli.py ingest ./docs/ --recursive

# 端到端问答
python cli.py ask "这段经验是什么意思？"
python cli.py ask "怎么处理 SSL 报错" --top-k 5

# 只检索片段（不调 LLM）
python cli.py query "类似的经验" --top-k 5

# 库管理
python cli.py list                         # 列出库内文档
python cli.py stats                         # 统计：文档数/chunk数/维度/embedder
python cli.py delete <source|doc_id>        # 删除某文档
python cli.py rebuild                       # 换 embedder 后重建（清空+重 ingest）
```

输出默认人类可读，加 `--json` 切机器可读。交互 REPL 模式（`chat`）列二期，v1 先做单次命令。

### REST API（`api.py`，FastAPI）

```python
POST /ingest        { "path": "./notes.md" }          # v1 仅本地路径模式
                    → { doc_id, chunk_count, source }

POST /query         { "question": "...", "top_k": 5 }
                    → { chunks: [{source, chunk_index, text, score}] }

POST /ask           { "question": "...", "top_k": 5 }
                    → { answer, sources: [{...}] }

GET  /documents                                      # 列出库内文档
GET  /documents/{doc_id}                             # 文档详情
DELETE /documents/{doc_id}                            # 删除文档

GET  /stats                                          # 库统计
GET  /health                                         # 健康检查
```

### 设计决策

1. **API 和 CLI 行为严格一致** —— 都调 `KnowledgeBase` 同一组方法，零业务逻辑，新增功能改一处即可。

2. **`/ingest` 双模式但 v1 只实现本地路径模式** —— 接口签名保留 `mode` 扩展点（路径/上传），v1 只实现 `{"path": ...}`（同机部署），上传模式（multipart 落盘、临时文件清理、安全校验）留到有跨机器需求时再补。

3. **用 FastAPI** —— ① 依赖已在 UTA 的 `.venv` 里，零新增依赖成本；② `/docs` 自动生成 OpenAPI，UTA 接入时照文档调；③ 异步原生，未来加流式输出顺理成章。

4. **不做鉴权**（v1）—— 本地单机自用。暴露网络时再加 token 中间件，不在 v1 范围。

5. **启动**：`python api.py` → `uvicorn rag.api:app`，默认 `127.0.0.1:8000`，端口在 `.env` 可配。

### UTA 未来接入示例

```python
# 路径 A：直接 import（同进程，最快）
from rag import KnowledgeBase
kb = KnowledgeBase()
answer = kb.ask(user_question)
chunks = kb.query(user_question)

# 路径 B：HTTP（跨进程/跨机器）
import requests
r = requests.post("http://localhost:8000/ask", json={"question": q})
```

两条路径同一套语义，UTA 按部署形态选。

## 8. 错误处理

**原则：快失败、明确报错、不静默吞。** 统一异常层级（`rag/errors.py`）：

```python
class KnowledgeBaseError(Exception): ...            # 基类

class UnsupportedSourceError(KnowledgeBaseError): ...   # Loader 不认识的扩展名
class EmbedderMismatchError(KnowledgeBaseError): ...    # 维度和库不一致
class EmptyStoreError(KnowledgeBaseError): ...          # 空库时 ask/query
class IngestError(KnowledgeBaseError): ...              # 文件读不出/切片失败
class LLMError(KnowledgeBaseError): ...                 # LLM 调用失败
```

| 场景 | 处理 |
|------|------|
| 空库 `ask`/`query` | 抛 `EmptyStoreError`，提示先 ingest |
| Embedder 维度 ≠ 库维度 | 启动即抛 `EmbedderMismatchError`，提示跑 `rebuild` |
| `ingest` 不支持的扩展名 | 抛 `UnsupportedSourceError`，列出支持类型；目录递归时跳过并记日志（不因一个文件中断整批） |
| LLM 调用超时/网络错 | 沿用 UTA 现有 `LLMClient` 的 curl fallback 策略，重试 2 次后抛 `LLMError` |
| SQLite 写入失败 | 事务回滚，`IngestError` 带原始异常 |

CLI/API 层转译：CLI = 友好中文提示 + 非零退出码；API = JSON `{error, detail}` + 对应 HTTP 码（4xx 客户端错、5xx 服务错）。

## 9. 测试策略（对齐 UTA 的 pytest 风格）

**每层独立单测，不依赖真实 LLM/embedding 网络。**

```
tests/
├── test_loaders.py        # TextLoader 读 MD/TXT、UnsupportedSource
├── test_chunkers.py       # 定长切片、重叠、短文档、边界
├── test_store.py          # 增删查、幂等去重、维度校验、事务回滚
├── test_retrieval.py      # 余弦相似度排序、top_k、空库
├── test_embeddings.py     # 用 fake embedder（固定向量）测接口契约
├── test_generation.py     # 用 fake generator 测 prompt 组装+引用
├── test_kb.py             # KnowledgeBase 端到端（全 fake 组件）
├── test_cli.py            # CLI 参数解析+输出格式
└── test_api.py            # FastAPI TestClient，/ingest /query /ask
```

### 测试设计要点

1. **`FakeEmbedder`/`FakeGenerator`** —— 嵌入层、生成层测试用固定返回的假实现，不碰网络、不下载模型，单测毫秒级。
2. **真实模型走单独的 `tests/integration/`** —— 标记 `@pytest.mark.integration`，CI 默认跳过，本地手动跑。
3. **`pytest` fixtures 提供临时 SQLite** —— `tmp_path` 每个测试独立库，不污染。
4. **覆盖率目标**：核心层（chunker/store/retrieval）≥ 90%，CLI/API ≥ 80%。

## 10. 分阶段路线图

按方案 3："接口一次到位，实现逐层铺开"。每阶段是可独立验证的里程碑。

| 阶段 | 名称 | 内容 | 验收 |
|------|------|------|------|
| v0.1-skeleton | 管线骨架 | 目录、`models.py`、`errors.py`、六层抽象接口、`KnowledgeBase` 装配默认组件（全 fake 实现）、单测跑通空链路 | `kb.ask("x")` 在空库抛 `EmptyStoreError`，接口契约确立 |
| v0.2-mvp | 最小可用 RAG | `TextLoader`（MD/TXT）+ `FixedChunker` + `LocalEmbedder`（bge-small-zh）+ `SqliteStore` + `VectorRetriever`，`ingest_path/query/ask` 跑通真实链路 | ingest 一个 MD → ask 一个问题 → 带来源返回答案 |
| v0.3-cli | CLI 完整 | `cli.py` 全部命令（ingest/query/ask/list/stats/delete/rebuild），人类可读输出 + `--json` | 命令行完整跑通日常用法 |
| v0.4-api | REST API | FastAPI 全部端点、OpenAPI 文档、错误处理 | `curl` 调通全流程，文档可读 |
| v0.5-content-types | 扩展内容类型 | `PdfLoader`、`DocxLoader`、（可选）`UrlLoader`，结构化数据（CSV/JSON）摄入策略 | 摄入 PDF/Word 也能正确切片检索 |
| v0.6-rerank | 检索质量增强 | `Reranker` 层（bge-reranker 重排）、混合检索（BM25 + 向量）作为 Retriever 新实现 | 复杂查询召回质量对比 v0.2 提升 |
| v0.7-uta-bridge | 接入 UTA | UTA 侧加 `KnowledgeRetrieverTool` 或集成进 Planner，端到端触发知识库检索 | UTA 跑一个需要外部知识的任务，用到了 RAG |

### 不在路线图内（YAGNI）

多用户/鉴权、分布式、Web 前端、流式输出、对话记忆——出现真实需求再考虑。
