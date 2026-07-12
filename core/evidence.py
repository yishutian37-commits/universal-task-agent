from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from core.state import Action, ToolResult


EVIDENCE_BUCKETS = ("files", "changes", "artifacts")
MUTATING_TOOL_NAMES = {
    "langchain_directory_create_tool",
    "langchain_file_delete_tool",
    "langchain_file_write_tool",
    "langchain_shell_tool",
}
SNAPSHOT_SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}
MAX_HASH_BYTES = 2_000_000
MAX_SNAPSHOT_ENTRIES = 5000


def empty_evidence() -> dict[str, list[dict[str, Any]]]:
    return {bucket: [] for bucket in EVIDENCE_BUCKETS}


def normalize_evidence(payload: Any) -> dict[str, list[dict[str, Any]]]:
    normalized = empty_evidence()
    if not isinstance(payload, dict):
        return normalized
    for bucket in EVIDENCE_BUCKETS:
        values = payload.get(bucket)
        if isinstance(values, list):
            normalized[bucket] = [dict(item) for item in values if isinstance(item, dict)]
    return normalized


def should_snapshot_tool(tool_name: str) -> bool:
    return str(tool_name or "") in MUTATING_TOOL_NAMES


def snapshot_workspace(root: Path | str | None) -> dict[str, dict[str, Any]]:
    if root is None:
        return {}
    workspace = Path(root).expanduser().resolve()
    if not workspace.is_dir():
        return {}

    snapshot: dict[str, dict[str, Any]] = {}
    for current_root, directories, filenames in os.walk(workspace, followlinks=False):
        directories[:] = sorted(
            name for name in directories if name not in SNAPSHOT_SKIP_DIRECTORIES and not name.startswith(".uta-")
        )
        current = Path(current_root)
        for name in directories:
            path = current / name
            if path.is_symlink():
                continue
            snapshot[path.relative_to(workspace).as_posix()] = {"kind": "directory"}
            if len(snapshot) >= MAX_SNAPSHOT_ENTRIES:
                return snapshot
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entry = {
                "kind": "file",
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
            if stat.st_size <= MAX_HASH_BYTES:
                try:
                    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    pass
            snapshot[path.relative_to(workspace).as_posix()] = entry
            if len(snapshot) >= MAX_SNAPSHOT_ENTRIES:
                return snapshot
    return snapshot


def diff_workspace_snapshots(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    root: Path | str,
    *,
    tool_name: str,
    step_id: int | None,
) -> list[dict[str, Any]]:
    workspace = Path(root).expanduser().resolve()
    changes = []
    for relative_path in sorted(set(before) | set(after)):
        old = before.get(relative_path)
        new = after.get(relative_path)
        if old is None:
            change_type = "created"
        elif new is None:
            change_type = "deleted"
        elif old.get("kind") == "directory" and new.get("kind") == "directory":
            continue
        elif old == new:
            continue
        else:
            change_type = "modified"

        current = new or old or {}
        changes.append(
            {
                "path": str((workspace / relative_path).resolve()),
                "change_type": change_type,
                "kind": str(current.get("kind") or "file"),
                "tool_name": tool_name,
                "step_id": step_id,
                "exists": change_type != "deleted",
                "before": dict(old or {}),
                "after": dict(new or {}),
            }
        )
    return changes


def collect_tool_evidence(
    action: Action,
    result: ToolResult,
    *,
    workspace_path: Path | str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    evidence = empty_evidence()
    if not result.success:
        return evidence

    payload = result.result if isinstance(result.result, dict) else {}
    workspace = Path(workspace_path).expanduser().resolve() if workspace_path else None
    tool_name = result.tool_name
    step_id = result.step_id if result.step_id is not None else action.step_id

    source_type = str(payload.get("source_type") or "")
    source = payload.get("source")
    if source_type in {"file", "directory"} and isinstance(source, str) and source:
        evidence["files"].append(
            _file_record(_resolve_path(source, workspace), "read", source_type, tool_name, step_id)
        )
    elif tool_name == "table_tool" and isinstance(source, str) and source:
        evidence["files"].append(_file_record(_resolve_path(source, workspace), "read", "file", tool_name, step_id))

    if tool_name == "code_tool":
        project_root = _resolve_path(str(payload.get("project_root") or workspace or ""), workspace)
        for item in payload.get("files") or []:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            evidence["files"].append(
                _file_record(_resolve_path(str(item["path"]), Path(project_root)), "read", "file", tool_name, step_id)
            )

    target = payload.get("path")
    if isinstance(target, str) and target:
        target_path = _resolve_path(target, workspace)
        if tool_name == "langchain_directory_create_tool":
            evidence["files"].append(_file_record(target_path, "verify", "directory", tool_name, step_id))
            if payload.get("created") is True:
                evidence["changes"].append(_change_record(target_path, "created", "directory", tool_name, step_id))
        elif tool_name == "langchain_file_write_tool":
            mode = str(payload.get("mode") or "create")
            change_type = "created" if mode == "create" else "modified"
            evidence["files"].append(_file_record(target_path, "write", "file", tool_name, step_id))
            evidence["changes"].append(_change_record(target_path, change_type, "file", tool_name, step_id))
            evidence["artifacts"].append(
                _file_artifact(target_path, tool_name, step_id, bytes_written=payload.get("bytes_written"))
            )
        elif tool_name == "langchain_file_delete_tool":
            restore_path = str(payload.get("trash_path") or "")
            evidence["files"].append(_file_record(target_path, "delete", "file", tool_name, step_id))
            record = _change_record(target_path, "deleted", "file", tool_name, step_id)
            if restore_path:
                record["restore_path"] = _resolve_path(restore_path, workspace)
            evidence["changes"].append(record)

    report = payload.get("report_markdown")
    if tool_name == "report_tool" and not isinstance(report, str):
        report = payload.get("message")
    if tool_name == "report_tool" and isinstance(report, str) and report.strip():
        evidence["artifacts"].append(
            {
                "artifact_id": _artifact_id("report", tool_name, "", step_id),
                "kind": "report",
                "label": "任务报告",
                "path": "",
                "tool_name": tool_name,
                "step_id": step_id,
                "verified": True,
                "content_preview": report.strip()[:500],
            }
        )
    return evidence


def artifacts_from_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts = []
    for change in changes:
        if change.get("kind") != "file" or change.get("change_type") not in {"created", "modified"}:
            continue
        path = str(change.get("path") or "")
        if not path:
            continue
        artifacts.append(
            _file_artifact(
                path,
                str(change.get("tool_name") or "workspace"),
                change.get("step_id"),
            )
        )
    return artifacts


def merge_evidence(
    target: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    added = empty_evidence()
    for bucket in EVIDENCE_BUCKETS:
        target.setdefault(bucket, [])
        known = {
            _record_key(bucket, item): item
            for item in target[bucket]
            if isinstance(item, dict)
        }
        for item in incoming.get(bucket, []):
            if not isinstance(item, dict):
                continue
            key = _record_key(bucket, item)
            if key in known:
                existing = known[key]
                for field, value in item.items():
                    if field not in existing or existing[field] in (None, "", 0, False):
                        existing[field] = value
                continue
            record = dict(item)
            target[bucket].append(record)
            added[bucket].append(record)
            known[key] = record
    return added


def _file_record(path: str, operation: str, kind: str, tool_name: str, step_id: int | None) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    return {
        "path": str(resolved),
        "operation": operation,
        "kind": kind,
        "tool_name": tool_name,
        "step_id": step_id,
        "exists": resolved.exists(),
    }


def _change_record(path: str, change_type: str, kind: str, tool_name: str, step_id: int | None) -> dict[str, Any]:
    return {
        "path": str(Path(path).expanduser().resolve()),
        "change_type": change_type,
        "kind": kind,
        "tool_name": tool_name,
        "step_id": step_id,
        "exists": change_type != "deleted",
    }


def _file_artifact(
    path: str,
    tool_name: str,
    step_id: int | None,
    *,
    bytes_written: Any = None,
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    return {
        "artifact_id": _artifact_id("file", tool_name, str(resolved), step_id),
        "kind": "file",
        "label": resolved.name,
        "path": str(resolved),
        "tool_name": tool_name,
        "step_id": step_id,
        "verified": resolved.is_file(),
        "bytes_written": int(bytes_written or 0),
    }


def _resolve_path(value: str, base: Path | None) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    return str(path.resolve())


def _artifact_id(kind: str, tool_name: str, path: str, step_id: int | None) -> str:
    raw = f"{kind}|{tool_name}|{path}|{step_id}"
    return "artifact_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _record_key(bucket: str, item: dict[str, Any]) -> tuple[Any, ...]:
    if bucket == "files":
        return (item.get("path"), item.get("operation"), item.get("tool_name"), item.get("step_id"))
    if bucket == "changes":
        return (item.get("path"), item.get("change_type"), item.get("tool_name"), item.get("step_id"))
    return (item.get("artifact_id") or item.get("path"), item.get("kind"), item.get("tool_name"), item.get("step_id"))
