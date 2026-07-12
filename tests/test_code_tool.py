from pathlib import Path

import pytest

from tools.code_tool import CodeTool


def write_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_code_tool_scans_imports_classes_and_functions(tmp_path):
    write_file(
        tmp_path,
        "main.py",
        "\n".join(
            [
                "import argparse",
                "from core.loop import run_minimal_loop",
                "",
                "class CliRunner:",
                "    pass",
                "",
                "def run_task():",
                "    return None",
                "",
                "def main():",
                "    return None",
            ]
        ),
    )
    write_file(
        tmp_path,
        "core/loop.py",
        "class LoopRunner:\n    pass\n\ndef run_minimal_loop():\n    return None\n",
    )
    write_file(tmp_path, "core/router.py", "class Router:\n    pass\n")
    write_file(tmp_path, "core/verifier.py", "class Verifier:\n    pass\n")

    result = CodeTool(
        project_root=tmp_path,
        key_files=["main.py", "core/loop.py", "core/router.py", "core/verifier.py"],
    ).run("scan", {})

    assert result["code_analysis"] is True
    assert result["focus"] == "task_flow"
    assert result["required_files"] == ["main.py", "core/loop.py", "core/router.py", "core/verifier.py"]

    main_info = next(item for item in result["files"] if item["path"] == "main.py")
    assert main_info["role"] == "CLI 入口与任务运行编排"
    assert "argparse" in main_info["imports"]
    assert "core.loop.run_minimal_loop" in main_info["imports"]
    assert main_info["classes"] == ["CliRunner"]
    assert main_info["functions"] == ["run_task", "main"]


def test_code_tool_fails_when_key_file_is_missing(tmp_path):
    with pytest.raises(ValueError, match="关键代码文件不存在：main.py"):
        CodeTool(project_root=tmp_path, key_files=["main.py"]).run("scan", {})


def test_code_tool_reports_syntax_errors(tmp_path):
    write_file(tmp_path, "main.py", "def broken(:\n    pass\n")

    with pytest.raises(ValueError, match="代码文件无法解析：main.py"):
        CodeTool(project_root=tmp_path, key_files=["main.py"]).run("scan", {})


def test_code_tool_discovers_generic_node_project(tmp_path):
    write_file(tmp_path, "package.json", '{"name": "demo-app"}')
    write_file(
        tmp_path,
        "src/index.js",
        "import { start } from './server.js';\nclass App {}\nfunction main() { start(); }\n",
    )
    write_file(tmp_path, "node_modules/ignored.js", "function ignored() {}\n")

    result = CodeTool(project_root=tmp_path).run("scan", {})

    assert result["project_kind"] == "generic"
    assert result["focus"] == "project_structure"
    assert [item["path"] for item in result["files"]] == ["package.json", "src/index.js"]
    index_info = result["files"][1]
    assert index_info["classes"] == ["App"]
    assert index_info["functions"] == ["main"]
    assert index_info["imports"] == ["./server.js"]


def test_code_tool_reports_when_generic_workspace_has_no_supported_project_files(tmp_path):
    write_file(tmp_path, "notes.txt", "plain notes")

    with pytest.raises(ValueError, match="未发现可分析的项目代码或清单文件"):
        CodeTool(project_root=tmp_path).run("scan", {})
