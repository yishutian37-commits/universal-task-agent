import json

from evals.runner import evaluate_cases, load_cases


def test_core_chinese_scenarios_pass_offline_evaluation():
    cases = load_cases()

    report = evaluate_cases(cases, live_model=False)

    assert report["total"] >= 12
    assert report["failed"] == 0
    assert report["passed"] == report["total"]


def test_evaluation_report_explains_failed_expectations(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "wrong_expectation",
                    "input": "你好",
                    "expect": {"message_kind": "task"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = evaluate_cases(load_cases(cases_path), live_model=False)

    assert report["failed"] == 1
    assert report["results"][0]["failures"][0]["field"] == "message_kind"
