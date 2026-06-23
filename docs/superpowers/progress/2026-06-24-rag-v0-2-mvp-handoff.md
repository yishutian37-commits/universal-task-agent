# RAG 知识库 v0.2-mvp 交接记录

时间：2026-06-24

## 当前状态

- 分支：`rag-knowledge-base`
- 当前 HEAD：`8b6fbfb feat: add from_config and v0.2 acceptance`
- RAG `v0.2-mvp` 已完成：真实文件摄入、切片、SQLite 持久化、向量检索、默认 KB 装配和端到端问答。

## 已完成能力

- `TextLoader`：读取 `.md` / `.txt` 文件。
- `FixedChunker`：按字符数定长切片，支持重叠。
- `HashingEmbedder`：确定性临时向量，用于验证管线。
- `SqliteStore`：SQLite 保存 documents / chunks / kb_meta，向量以 BLOB 存储。
- `VectorRetriever`：numpy 余弦相似度 top-k 检索。
- `EchoGenerator`：临时回显生成器，输出问题、来源和片段。
- `create_default_kb()` / `KnowledgeBase.from_config()`：默认装配一条可用管线。

## 验证

全量 RAG 测试：

```bash
/Users/tianjiashu/项目/.venv/bin/python -m pytest rag-knowledge-base/tests -q
```

结果：

```text
71 passed in 0.05s
```

端到端冒烟：

```bash
PYTHONPATH=/Users/tianjiashu/项目/rag-knowledge-base \
/Users/tianjiashu/项目/.venv/bin/python - <<'PY'
from rag import create_default_kb
kb = create_default_kb(db_path="/private/tmp/rag-v02-smoke/knowledge.db")
result = kb.ingest_path("/private/tmp/rag-v02-smoke/notes.md")
answer = kb.ask("RAG 给 UTA 提供什么能力？", top_k=1)
print(result)
print(answer.answer)
print("sources=", len(answer.sources))
PY
```

已验证：摄入真实 `.md` 文件后，`ask()` 可以返回答案和 1 个来源片段。

## 当前限制

- embedding 仍是 `HashingEmbedder`，不是语义向量。
- generator 仍是 `EchoGenerator`，没有调用真实 LLM。
- 尚无 `cli.py`，只能通过 Python API 使用。
- 尚无 `api.py` / FastAPI 入口。
- 仅支持 `.md` / `.txt`，暂不支持 PDF / Word / URL。

## 下一步

1. 打 `rag-v0.2-mvp` tag。
2. 编写并执行 `v0.3-cli` 计划。
3. CLI 完成后再进入 `v0.4-api` 或 `v0.2.5` 真实 embedding / LLM。
