from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rag.defaults import create_default_kb
from rag.evaluation import evaluate_retrieval


CASES_PATH = Path(__file__).with_name("eval_cases.json")


def run_builtin_benchmark() -> dict:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="uta-rag-eval-") as temp_dir:
        root = Path(temp_dir)
        kb = create_default_kb(db_path=str(root / "benchmark.db"))
        for document in payload.get("documents", []):
            path = root / str(document["source"])
            path.write_text(str(document["content"]), encoding="utf-8")
            kb.ingest_path(str(path))
        return evaluate_retrieval(kb, list(payload.get("queries", [])), top_k=3)


def main() -> int:
    report = run_builtin_benchmark()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
