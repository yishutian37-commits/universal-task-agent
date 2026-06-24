"""UTA 知识库自动摄入脚本。

把 UTA 的知识资产（README、设计文档、memory JSON、skills）一次性灌进
RAG 知识库。以后文档更新后重跑此脚本即可（ingest 幂等，按 source 去重）。

用法：
    python -m rag.seed                    # 用默认临时模型
    python -m rag.seed --real-models      # 用真实 bge + LLM
    python -m rag.seed --db-path custom.db
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 摄入目标：UTA 的核心知识资产
SEED_SOURCES = [
    # 根级文档
    "README.md",
    "CHANGELOG.md",
    # 设计 spec（架构决策的权威来源）
    "docs/project-overview.md",
    "docs/superpowers/specs/2026-06-24-rag-knowledge-base-design.md",
    "docs/superpowers/specs/2026-06-20-v0-1-skeleton-design.md",
    "docs/superpowers/specs/2026-06-20-v0-2-llm-parser-design.md",
    "docs/superpowers/specs/2026-06-20-v0-3-planner-router-design.md",
    "docs/superpowers/specs/2026-06-20-v0-4-summary-demo-design.md",
    "docs/superpowers/specs/2026-06-20-v0-5-verifier-reflection-design.md",
    "docs/superpowers/specs/2026-06-20-v0-6-data-analysis-design.md",
    "docs/superpowers/specs/2026-06-20-v0-7-memory-design.md",
    "docs/superpowers/specs/2026-06-21-v0-8-skill-runtime-design.md",
    "docs/superpowers/specs/2026-06-23-v1-0-learning-agent-memory-design.md",
    # Skills
    "skills/summarize_article.md",
    "skills/analyze_table.md",
    # memory JSON（经验、历史、规则——转成可读文本）
    "memory/lessons.json",
    "memory/task_history.json",
    "memory/negative_rules.json",
    "memory/skill_candidates.json",
    "memory/user_profile.json",
]


def _format_json_as_text(path: Path) -> str:
    """把 JSON 文件转成人类可读的 Markdown 文本，便于语义检索。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [f"# {path.name}", ""]

    if isinstance(data, list):
        for i, item in enumerate(data, 1):
            if isinstance(item, dict):
                lines.append(f"## 条目 {i}")
                for key, value in item.items():
                    lines.append(f"- **{key}**: {value}")
                lines.append("")
            else:
                lines.append(f"- {item}")
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"## {key}（{len(value)} 条）")
                for item in value:
                    if isinstance(item, dict):
                        summary = "；".join(f"{k}: {v}" for k, v in item.items())
                        lines.append(f"- {summary}")
                    else:
                        lines.append(f"- {item}")
            else:
                lines.append(f"- **{key}**: {value}")
        lines.append("")

    return "\n".join(lines)


def seed(
    db_path: str = "data/knowledge.db",
    use_real_models: bool = False,
) -> dict:
    """摄入所有 SEED_SOURCES 到知识库，返回统计。"""
    from rag.defaults import create_default_kb
    from rag.errors import KnowledgeBaseError

    kb = create_default_kb(db_path=db_path, use_real_models=use_real_models)

    # 需要把 JSON 转成文本的文件，用临时 LoadedDoc 直接喂
    from rag.loaders.base import LoadedDoc

    ingested = 0
    skipped = 0
    errors = []

    for rel_path in SEED_SOURCES:
        full = PROJECT_ROOT / rel_path
        if not full.exists():
            skipped += 1
            continue

        try:
            if full.suffix == ".json":
                # JSON 转可读文本，直接走 chunker（绕过 TextLoader 的扩展名检查）
                import os
                import uuid
                from datetime import datetime

                text = _format_json_as_text(full)
                source = str(full)
                # 幂等：先删旧
                kb._store.delete_by_source(source)
                doc_id = str(uuid.uuid4())
                chunks = kb.chunker.chunk_text(text, doc_id, source)
                vectors = kb.embedder.embed([c.text for c in chunks])
                kb._store.add(chunks, vectors)
                from rag.models import Document

                kb._store.upsert_doc(
                    Document(
                        doc_id=doc_id,
                        source=source,
                        title=full.stem,
                        type="json",
                        chunk_count=len(chunks),
                        ingested_at=datetime.now().isoformat(timespec="seconds"),
                        metadata={"original_format": "json"},
                    )
                )
                ingested += 1
            else:
                # .md 直接走标准 ingest
                kb.ingest_path(str(full))
                ingested += 1
        except KnowledgeBaseError as exc:
            errors.append(f"{rel_path}: {exc}")

    stats = kb.stats()
    return {
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
        **stats,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="UTA 知识库自动摄入")
    parser.add_argument("--db-path", default="data/knowledge.db")
    parser.add_argument("--real-models", action="store_true", help="用真实 bge + LLM")
    args = parser.parse_args()

    print("正在摄入 UTA 知识资产...")
    result = seed(db_path=args.db_path, use_real_models=args.real_models)
    print(f"完成：{result['ingested']} 个文档，{result['skipped']} 个跳过")
    if result["errors"]:
        print(f"错误（{len(result['errors'])} 个）：")
        for err in result["errors"]:
            print(f"  {err}")
    print(f"知识库：{result['documents']} 文档，{result['chunks']} 片段，{result['dim']} 维")
    return 0


if __name__ == "__main__":
    sys.exit(main())
