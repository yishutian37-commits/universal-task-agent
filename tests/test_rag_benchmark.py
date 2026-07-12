from rag.benchmark import run_builtin_benchmark


def test_builtin_rag_benchmark_reports_hit_rate_and_mrr():
    report = run_builtin_benchmark()

    assert report["total"] >= 3
    assert report["hit_at_k"] == 1.0
    assert report["mrr"] == 1.0
    assert all(case["passed"] for case in report["results"])
