from pathlib import Path

from core.evidence import (
    artifacts_from_changes,
    collect_tool_evidence,
    diff_workspace_snapshots,
    merge_evidence,
    snapshot_workspace,
)
from core.state import Action, ToolResult


def test_workspace_snapshot_detects_created_modified_and_deleted_paths(tmp_path):
    kept = tmp_path / "kept.txt"
    deleted = tmp_path / "deleted.txt"
    kept.write_text("before", encoding="utf-8")
    deleted.write_text("remove", encoding="utf-8")
    before = snapshot_workspace(tmp_path)

    kept.write_text("after", encoding="utf-8")
    deleted.unlink()
    created_dir = tmp_path / "new-folder"
    created_dir.mkdir()
    created = created_dir / "new.txt"
    created.write_text("new", encoding="utf-8")
    after = snapshot_workspace(tmp_path)

    changes = diff_workspace_snapshots(before, after, tmp_path, tool_name="test_tool", step_id=2)

    by_path = {Path(item["path"]).relative_to(tmp_path).as_posix(): item for item in changes}
    assert by_path["kept.txt"]["change_type"] == "modified"
    assert by_path["deleted.txt"]["change_type"] == "deleted"
    assert by_path["new-folder"]["change_type"] == "created"
    assert by_path["new-folder/new.txt"]["change_type"] == "created"
    assert all(item["tool_name"] == "test_tool" for item in changes)


def test_collect_tool_evidence_normalizes_reads_writes_and_reports(tmp_path):
    source = tmp_path / "source.md"
    output = tmp_path / "result.txt"
    source.write_text("source", encoding="utf-8")
    output.write_text("result", encoding="utf-8")

    read_action = Action("a1", 1, "file_tool", "read", {}, "read")
    read_result = ToolResult(
        True,
        "file_tool",
        "read",
        {"source_type": "file", "source": str(source), "message": "已读取"},
        step_id=1,
    )
    write_action = Action("a2", 2, "langchain_file_write_tool", "invoke", {}, "write")
    write_result = ToolResult(
        True,
        "langchain_file_write_tool",
        "invoke",
        {"path": str(output), "mode": "create", "bytes_written": 6},
        step_id=2,
    )
    report_action = Action("a3", 3, "report_tool", "render", {}, "report")
    report_result = ToolResult(
        True,
        "report_tool",
        "render",
        {"message": "## 结论\n完成", "report_markdown": "## 结论\n完成"},
        step_id=3,
    )

    read = collect_tool_evidence(read_action, read_result, workspace_path=tmp_path)
    write = collect_tool_evidence(write_action, write_result, workspace_path=tmp_path)
    report = collect_tool_evidence(report_action, report_result, workspace_path=tmp_path)

    assert read["files"][0]["path"] == str(source.resolve())
    assert read["files"][0]["operation"] == "read"
    assert write["changes"][0]["change_type"] == "created"
    assert write["artifacts"][0]["path"] == str(output.resolve())
    assert write["artifacts"][0]["verified"] is True
    assert report["artifacts"][0]["kind"] == "report"
    assert report["artifacts"][0]["verified"] is True


def test_merge_evidence_deduplicates_replayed_records():
    target = {"files": [], "changes": [], "artifacts": []}
    incoming = {
        "files": [{"path": "/tmp/a.txt", "operation": "read", "tool_name": "file_tool", "step_id": 1}],
        "changes": [{"path": "/tmp/a.txt", "change_type": "created", "tool_name": "write", "step_id": 2}],
        "artifacts": [{"artifact_id": "artifact-1", "kind": "file", "path": "/tmp/a.txt"}],
    }

    first = merge_evidence(target, incoming)
    second = merge_evidence(target, incoming)

    assert first == incoming
    assert second == {"files": [], "changes": [], "artifacts": []}
    assert {key: len(value) for key, value in target.items()} == {"files": 1, "changes": 1, "artifacts": 1}

    enriched = merge_evidence(
        target,
        {
            "files": [],
            "changes": [
                {
                    "path": "/tmp/a.txt",
                    "change_type": "created",
                    "tool_name": "write",
                    "step_id": 2,
                    "restore_path": "/tmp/trash/a.txt",
                }
            ],
            "artifacts": [],
        },
    )
    assert enriched == {"files": [], "changes": [], "artifacts": []}
    assert target["changes"][0]["restore_path"] == "/tmp/trash/a.txt"


def test_created_or_modified_workspace_files_become_verified_artifacts(tmp_path):
    output = tmp_path / "generated.md"
    output.write_text("generated", encoding="utf-8")
    changes = [
        {
            "path": str(output),
            "change_type": "created",
            "kind": "file",
            "tool_name": "langchain_shell_tool",
            "step_id": 1,
        },
        {
            "path": str(tmp_path / "folder"),
            "change_type": "created",
            "kind": "directory",
            "tool_name": "langchain_shell_tool",
            "step_id": 1,
        },
    ]

    artifacts = artifacts_from_changes(changes)

    assert len(artifacts) == 1
    assert artifacts[0]["path"] == str(output.resolve())
    assert artifacts[0]["verified"] is True
