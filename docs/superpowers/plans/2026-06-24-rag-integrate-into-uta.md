# RAG 知识库整合进 UTA 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `rag-knowledge-base/` 子目录整合进 UTA 根目录——`rag/` 包提到根（和 `core/` 平级），测试合并进 `tests/`，依赖并入根 `requirements.txt`，配置并入根 `.env.example` 和 `config.py`。整合后 71 个 RAG 测试 + 24 个 UTA 测试全部仍绿。

**Architecture:** 纯文件迁移 + import 路径调整。`rag/` 包内部都是 `from rag.xxx` 相对引用，迁移后路径不变，包内代码零改动。改动集中在：① 文件位置移动；② 测试文件从 `rag-knowledge-base/tests/` 挪到根 `tests/`（统一 `test_rag_` 前缀避免和 UTA 测试名冲突）；③ 根配置文件合并；④ 删除空的 `rag-knowledge-base/` 子目录。

**Tech Stack:** Python 3.12、git mv、pytest。

**前置状态:** v0.2-mvp 完成（commit `8b6fbfb`），分支 `rag-knowledge-base`，71 测试全绿。

**关键约束:**
- 每一步后都要跑测试确认不破坏现有功能
- UTA 根 `tests/` 无 `__init__.py`，平铺风格，RAG 测试合并时加 `test_rag_` 前缀
- `rag/` 包内 import 不动（都是 `from rag.xxx`）
- 根目录已有 `config.py` 读 `.env`，RAG 的配置项加进去而非新建

---

## 文件迁移映射

```
rag-knowledge-base/rag/            ──►  rag/                    （git mv，包整体）
rag-knowledge-base/tests/test_*.py ──►  tests/test_rag_*.py      （加前缀）
rag-knowledge-base/tests/conftest.py ──► tests/conftest_rag.py   （合并而非替换根 conftest）
rag-knowledge-base/tests/__init__.py  ──► 删除（根 tests/ 无 __init__）
rag-knowledge-base/requirements.txt   ──► 合并入根 requirements.txt
rag-knowledge-base/.env.example       ──► 合并入根 .env.example
rag-knowledge-base/README.md          ──► 移到 rag/README.md
rag-knowledge-base/.gitignore         ──► 删除（根 .gitignore 已有 data/）
rag-knowledge-base/                   ──► 删除空目录
```

---

### Task 1: 移动 rag/ 包到根目录

**Files:**
- Move: `rag-knowledge-base/rag/` → `rag/`

- [ ] **Step 1: git mv 移动 rag 包**

```bash
cd /Users/tianjiashu/项目
git mv rag-knowledge-base/rag rag
```

- [ ] **Step 2: 验证包结构完整**

Run: `ls rag/`
Expected: 看到 `__init__.py kb.py models.py errors.py defaults.py` 和 `loaders/ chunkers/ embeddings/ store/ retrieval/ generation/` 六个子目录

- [ ] **Step 3: 验证包能正常 import**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -c "from rag import KnowledgeBase; print('OK', KnowledgeBase)"`
Expected: `OK <class 'rag.kb.KnowledgeBase'>`

> 注意：此时 rag/ 内部 import 都是 `from rag.xxx`，移动后仍正确，因为包名没变。

- [ ] **Step 4: Commit**

```bash
git add rag/ rag-knowledge-base/rag/
git commit -m "refactor: move rag package to project root"
```

---

### Task 2: 移动并重命名 RAG 测试文件

**Files:**
- Move: `rag-knowledge-base/tests/*.py` → `tests/test_rag_*.py`

UTA 根 `tests/` 是平铺的，RAG 测试要合并进去。为避免和 UTA 的 `test_models.py`、`test_errors.py` 等同名冲突，统一加 `test_rag_` 前缀。

- [ ] **Step 1: 移动测试文件（加前缀）**

逐个 git mv（保持 git 历史）：

```bash
cd /Users/tianjiashu/项目

git mv rag-knowledge-base/tests/test_models.py tests/test_rag_models.py
git mv rag-knowledge-base/tests/test_errors.py tests/test_rag_errors.py
git mv rag-knowledge-base/tests/test_loaders_base.py tests/test_rag_loaders_base.py
git mv rag-knowledge-base/tests/test_chunkers_base.py tests/test_rag_chunkers_base.py
git mv rag-knowledge-base/tests/test_embeddings_base.py tests/test_rag_embeddings_base.py
git mv rag-knowledge-base/tests/test_store_base.py tests/test_rag_store_base.py
git mv rag-knowledge-base/tests/test_retrieval_base.py tests/test_rag_retrieval_base.py
git mv rag-knowledge-base/tests/test_generation_base.py tests/test_rag_generation_base.py
git mv rag-knowledge-base/tests/test_kb.py tests/test_rag_kb.py
git mv rag-knowledge-base/tests/test_package.py tests/test_rag_package.py
git mv rag-knowledge-base/tests/test_text_loader.py tests/test_rag_text_loader.py
git mv rag-knowledge-base/tests/test_fixed_chunker.py tests/test_rag_fixed_chunker.py
git mv rag-knowledge-base/tests/test_hashing_embedder.py tests/test_rag_hashing_embedder.py
git mv rag-knowledge-base/tests/test_sqlite_store.py tests/test_rag_sqlite_store.py
git mv rag-knowledge-base/tests/test_vector_retriever.py tests/test_rag_vector_retriever.py
git mv rag-knowledge-base/tests/test_defaults.py tests/test_rag_defaults.py
```

- [ ] **Step 2: 处理 conftest.py**

RAG 的 `conftest.py` 定义了 `fake_components` fixture，UTA 根目录没有 conftest。直接移动：

```bash
cd /Users/tianjiashu/项目
git mv rag-knowledge-base/tests/conftest.py tests/conftest.py
```

> 验证：确认根目录原本无 conftest.py（前面已查实），不会覆盖。

- [ ] **Step 3: 删除 tests/__init__.py**

RAG 的 `tests/__init__.py` 是空文件，UTA 根 `tests/` 不用 `__init__.py`（pytest 自动发现）。删除保持一致：

```bash
cd /Users/tianjiashu/项目
git rm rag-knowledge-base/tests/__init__.py
```

- [ ] **Step 4: 验证测试文件已就位**

Run: `ls tests/test_rag_*.py | wc -l`
Expected: 16

- [ ] **Step 5: 暂不提交——先确认测试能跑（见 Task 3）**

---

### Task 3: 修复测试中的 data/ 路径引用 + 运行全部测试

**问题预判：** RAG 的 `.gitignore` 排除了 `data/`，测试和 defaults.py 用 `data/knowledge.db` 默认路径。整合后 data/ 仍在项目根，需确认路径正确。

**Files:**
- 可能 Modify: `rag/defaults.py`（确认 db_path 默认值）

- [ ] **Step 1: 检查 defaults.py 的 db_path 默认值**

Run: `grep -n "db_path" /Users/tianjiashu/项目/rag/defaults.py`
确认默认是 `data/knowledge.db`——这个路径相对于项目根（cwd），整合后仍正确，因为 UTA 也是从项目根运行的。

- [ ] **Step 2: 运行全部 RAG 测试**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -m pytest tests/test_rag_*.py tests/conftest.py -v 2>&1 | tail -10`
Expected: 71 passed（测试文件改名了，但内容没变，import 仍是 `from rag.xxx`，包在根目录所以正确）

- [ ] **Step 3: 运行 UTA 原有测试，确认未受影响**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -m pytest tests/ -v --ignore-glob='tests/test_rag_*' 2>&1 | tail -10`
Expected: UTA 的 24 个测试仍全绿

> 注意：如果 conftest.py 的 `fake_components` fixture 被 UTA 测试误触发，需检查是否有命名冲突。`fake_components` 是 RAG 专用名，UTA 不应使用。

- [ ] **Step 4: 运行全部测试（UTA + RAG）**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5`
Expected: 71 + UTA 测试数 = 全绿

- [ ] **Step 5: Commit 测试迁移**

```bash
cd /Users/tianjiashu/项目
git add tests/
git commit -m "refactor: merge rag tests into root tests/ with test_rag_ prefix"
```

---

### Task 4: 合并 requirements.txt

**Files:**
- Modify: `requirements.txt`（根）
- Delete: `rag-knowledge-base/requirements.txt`

- [ ] **Step 1: 合并依赖**

根 `requirements.txt` 当前：
```
pytest>=8.0.0
pandas>=2.0.0
openpyxl>=3.1.0
certifi>=2024.0.0
```

RAG 需要额外：`numpy>=2.0.0`（pytest 已有）。写入根 `requirements.txt`：

```
pytest>=8.0.0
pandas>=2.0.0
openpyxl>=3.1.0
numpy>=2.0.0
certifi>=2024.0.0
```

- [ ] **Step 2: 删除 RAG 独立 requirements.txt**

```bash
cd /Users/tianjiashu/项目
git rm rag-knowledge-base/requirements.txt
```

- [ ] **Step 3: 验证 numpy 已在 venv**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -c "import numpy; print(numpy.__version__)"`
Expected: 2.3.5

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "refactor: merge rag requirements into root requirements.txt"
```

---

### Task 5: 合并配置（.env.example + config.py）

**Files:**
- Modify: `.env.example`
- Modify: `config.py`
- Delete: `rag-knowledge-base/.env.example`

- [ ] **Step 1: 更新 .env.example，加 RAG 配置项**

在根 `.env.example` 末尾追加 RAG 配置段（保留原有 LLM 配置不重复）：

```
# RAG 知识库
EMBED_PROVIDER=local
EMBED_MODEL=BAAI/bge-small-zh-v1.5
EMBED_DIM=512
EMBED_API_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1/embeddings
KB_DB_PATH=data/knowledge.db
KB_API_HOST=127.0.0.1
KB_API_PORT=8000
```

> 注意：LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 已在原文件里，RAG 复用，不重复加。

- [ ] **Step 2: 更新 config.py，加 KB_DB_PATH 等**

在 `config.py` 的 `TAM_DB_PATH = ...` 行之后，追加：

```python
KB_DB_PATH = os.getenv("KB_DB_PATH", "data/knowledge.db")
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "local")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
EMBED_DIM = int(os.getenv("EMBED_DIM", "512"))
KB_API_HOST = os.getenv("KB_API_HOST", "127.0.0.1")
KB_API_PORT = int(os.getenv("KB_API_PORT", "8000"))
```

- [ ] **Step 3: 删除 RAG 独立 .env.example**

```bash
cd /Users/tianjiashu/项目
git rm rag-knowledge-base/.env.example
```

- [ ] **Step 4: 验证 config 能读到新配置**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -c "from config import KB_DB_PATH; print(KB_DB_PATH)"`
Expected: `data/knowledge.db`

- [ ] **Step 5: Commit**

```bash
git add .env.example config.py
git commit -m "refactor: merge rag config into root .env.example and config.py"
```

---

### Task 6: 清理 RAG 子目录残留 + README 迁移

**Files:**
- Move: `rag-knowledge-base/README.md` → `rag/README.md`
- Delete: `rag-knowledge-base/`（剩余空目录）

- [ ] **Step 1: 移动 RAG README**

```bash
cd /Users/tianjiashu/项目
git mv rag-knowledge-base/README.md rag/README.md
```

- [ ] **Step 2: 删除 .gitignore（根已有）**

```bash
cd /Users/tianjiashu/项目
git rm rag-knowledge-base/.gitignore
```

- [ ] **Step 3: 检查子目录是否已空**

Run: `ls -la rag-knowledge-base/ 2>&1`
Expected: 空目录或不存在。如果有残留的 `__pycache__` 或 `data/`，手动清理：
```bash
rm -rf rag-knowledge-base/
```

- [ ] **Step 4: 确认根 .gitignore 包含 data/**

Run: `grep -n "data" /Users/tianjiashu/项目/.gitignore`
如果根 .gitignore 没有 data/，则加上。

- [ ] **Step 5: Commit**

```bash
cd /Users/tianjiashu/项目
git add -A rag-knowledge-base rag/README.md
git commit -m "refactor: move rag readme, remove rag-knowledge-base subdirectory"
```

---

### Task 7: 最终验证 + README 更新

**Files:**
- Modify: `README.md`（根，加 RAG 说明）

- [ ] **Step 1: 全量测试**

Run: `cd /Users/tianjiashu/项目 && .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5`
Expected: 全绿（UTA + RAG 所有测试）

- [ ] **Step 2: import 冒烟**

Run:
```bash
cd /Users/tianjiashu/项目
.venv/bin/python -c "from rag import KnowledgeBase, create_default_kb; print('rag OK')"
.venv/bin/python -c "from core.loop import run_minimal_loop; print('uta OK')"
```
Expected: 两行 OK，无 import 错误

- [ ] **Step 3: 端到端冒烟（RAG 从根目录运行）**

Run:
```bash
cd /Users/tianjiashu/项目
mkdir -p /tmp/rag-int-smoke
printf 'UTA 是学习型 Agent 框架。支持总结和表格分析。\n' > /tmp/rag-int-smoke/notes.md
.venv/bin/python -c "
from rag import create_default_kb
kb = create_default_kb(db_path='/tmp/rag-int-smoke/kb.db')
kb.ingest_path('/tmp/rag-int-smoke/notes.md')
ans = kb.ask('UTA 是什么')
print('ANSWER:', ans.answer[:80])
print('SOURCES:', len(ans.sources))
"
```
Expected: 打印含 "UTA" 的答案，sources >= 1

- [ ] **Step 4: 更新根 README，加 RAG 模块说明**

在根 `README.md` 适当位置加一段：

```markdown
## RAG 知识库

`rag/` 模块提供文档摄入、向量检索和问答能力，可独立使用，也可供 Agent 调用。

\```python
from rag import create_default_kb
kb = create_default_kb()
kb.ingest_path("notes.md")
print(kb.ask("问题").answer)
\```

详见 `rag/README.md` 和 `docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md`。
```

- [ ] **Step 5: Commit**

```bash
cd /Users/tianjiashu/项目
git add README.md
git commit -m "docs: document rag module in root readme"
```

---

## 自检结果

**1. 覆盖检查：**
- ✅ rag/ 包移动 → Task 1
- ✅ 测试合并（16 文件 + conftest）→ Task 2-3
- ✅ 依赖合并 → Task 4
- ✅ 配置合并（.env.example + config.py）→ Task 5
- ✅ 子目录清理 + README → Task 6
- ✅ 最终验证 + 根 README → Task 7

**2. 风险点：**
- conftest.py 的 `fake_components` fixture 可能被 UTA 测试误用 → Task 3 Step 3 会验证，fixture 名不冲突
- data/ 路径 → defaults.py 用相对路径 `data/knowledge.db`，从根目录运行正确
- 测试文件重名 → 加 `test_rag_` 前缀彻底避免

**3. 不改动的：**
- `rag/` 包内所有 `.py` 文件的 import（都是 `from rag.xxx`，移动后仍正确）
- UTA 现有代码（core/、tools/、llm/ 等零改动）
