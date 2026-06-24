from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag.errors import EmptyStoreError, KnowledgeBaseError
from rag.kb import KnowledgeBase


def _build_kb(args: argparse.Namespace) -> KnowledgeBase:
    return KnowledgeBase.from_config(
        db_path=args.db_path,
    )


def _print(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _print_human(data)


def _print_human(data) -> None:
    if isinstance(data, dict):
        if "doc_id" in data:
            print(f"已摄入：{data['source']}（{data['chunk_count']} 个片段）")
            print(f"  doc_id: {data['doc_id']}")
            return
        if "documents" in data and "chunks" in data and "dim" in data:
            print(f"文档数：{data['documents']}")
            print(f"片段数：{data['chunks']}")
            print(f"维度：{data['dim']}")
            return
        if "deleted" in data:
            print(f"已删除 {data['deleted']} 条（目标：{data['target']}）")
            return
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "doc_id" in data[0]:
            print(f"文档列表（{len(data)} 个）：")
            for doc in data:
                print(f"  {doc['doc_id']}  {doc['source']}  ({doc['chunk_count']} 片段)")
            return
        # query 结果
        for i, item in enumerate(data, 1):
            score = item.get("score", 0)
            source = item.get("source", "?")
            text = item.get("text", "")
            print(f"[{i}] (score={score:.3f}, {source})")
            print(f"    {text[:100]}")
        return
    print(data)


def _format_doc(doc) -> dict:
    return {
        "doc_id": doc.doc_id,
        "source": doc.source,
        "title": doc.title,
        "type": doc.type,
        "chunk_count": doc.chunk_count,
        "ingested_at": doc.ingested_at,
    }


def _format_retrieved(rc) -> dict:
    return {
        "score": round(rc.score, 4),
        "source": rc.chunk.source,
        "chunk_index": rc.chunk.chunk_index,
        "text": rc.chunk.text,
    }


def cmd_ingest(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    path = Path(args.path)
    if path.is_dir():
        if not args.recursive:
            files = sorted(path.glob("*.md")) + sorted(path.glob("*.txt"))
        else:
            files = sorted(path.rglob("*.md")) + sorted(path.rglob("*.txt"))
        results = []
        for f in files:
            try:
                results.append(kb.ingest_path(str(f)))
            except KnowledgeBaseError as exc:
                print(f"跳过 {f}: {exc}", file=sys.stderr)
        _print(results, args.json)
        return 0
    else:
        result = kb.ingest_path(args.path)
        _print(result, args.json)
        return 0


def cmd_query(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    try:
        retrieved = kb.query(args.question, top_k=args.top_k)
    except EmptyStoreError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    data = [_format_retrieved(r) for r in retrieved]
    _print(data, args.json)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    try:
        answer = kb.ask(args.question, top_k=args.top_k)
    except EmptyStoreError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "answer": answer.answer,
                    "sources": [_format_retrieved(r) for r in answer.sources],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(answer.answer)
        if answer.sources:
            print("\n来源：")
            for i, r in enumerate(answer.sources, 1):
                print(f"  [{i}] {r.chunk.source} (score={r.score:.3f})")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    docs = kb.list_docs()
    data = [_format_doc(d) for d in docs]
    _print(data, args.json)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    _print(kb.stats(), args.json)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    kb = _build_kb(args)
    result = kb.delete(args.target)
    _print(result, args.json)
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    if not args.yes:
        print("警告：这将清空整个知识库。加 --yes 确认。", file=sys.stderr)
        return 1
    kb = _build_kb(args)
    result = kb.rebuild()
    _print(result, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag",
        description="RAG 知识库命令行工具",
    )
    parser.add_argument("--db-path", default="data/knowledge.db", help="SQLite 数据库路径")
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="摄入文档")
    p_ingest.add_argument("path", help="文件或目录路径")
    p_ingest.add_argument("--recursive", "-r", action="store_true", help="递归摄入目录")
    p_ingest.add_argument("--json", action="store_true", help="JSON 输出")
    p_ingest.set_defaults(func=cmd_ingest)

    # query
    p_query = sub.add_parser("query", help="检索片段（不调 LLM）")
    p_query.add_argument("question", help="查询问题")
    p_query.add_argument("--top-k", type=int, default=5, help="返回片段数")
    p_query.add_argument("--json", action="store_true", help="JSON 输出")
    p_query.set_defaults(func=cmd_query)

    # ask
    p_ask = sub.add_parser("ask", help="端到端问答（检索 + LLM 生成）")
    p_ask.add_argument("question", help="问题")
    p_ask.add_argument("--top-k", type=int, default=5, help="检索片段数")
    p_ask.add_argument("--json", action="store_true", help="JSON 输出")
    p_ask.set_defaults(func=cmd_ask)

    # list
    p_list = sub.add_parser("list", help="列出库内文档")
    p_list.add_argument("--json", action="store_true", help="JSON 输出")
    p_list.set_defaults(func=cmd_list)

    # stats
    p_stats = sub.add_parser("stats", help="库统计")
    p_stats.add_argument("--json", action="store_true", help="JSON 输出")
    p_stats.set_defaults(func=cmd_stats)

    # delete
    p_delete = sub.add_parser("delete", help="删除文档")
    p_delete.add_argument("target", help="doc_id 或 source 路径")
    p_delete.add_argument("--json", action="store_true", help="JSON 输出")
    p_delete.set_defaults(func=cmd_delete)

    # rebuild
    p_rebuild = sub.add_parser("rebuild", help="清空知识库")
    p_rebuild.add_argument("--yes", action="store_true", help="确认清空")
    p_rebuild.add_argument("--json", action="store_true", help="JSON 输出")
    p_rebuild.set_defaults(func=cmd_rebuild)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KnowledgeBaseError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
