import pytest

from tools.file_tool import FileTool


def test_file_tool_reads_text_file_from_task(tmp_path):
    source = tmp_path / "meeting.txt"
    source.write_text("会议记录：上线前检查库存接口。", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"帮我总结 {source}"})

    assert result["content"] == "会议记录：上线前检查库存接口。"
    assert result["source_type"] == "file"
    assert result["source"] == str(source)
    assert result["message"] == "已读取文本内容"


def test_file_tool_reads_csv_path_as_table_file(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("order_id,quantity\n1,2\n", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"分析 {csv_path}"})

    assert result["message"] == "已读取表格文件"
    assert result["source_type"] == "file"
    assert result["file_kind"] == "table"
    assert result["source"] == str(csv_path)
    assert "content" not in result


def test_file_tool_reads_xlsx_path_as_table_file(tmp_path):
    xlsx_path = tmp_path / "orders.xlsx"
    xlsx_path.write_text("xlsx marker", encoding="utf-8")

    result = FileTool().run("read", {"user_input": f"分析 {xlsx_path}"})

    assert result["message"] == "已读取表格文件"
    assert result["file_kind"] == "table"
    assert result["source"] == str(xlsx_path)


def test_file_tool_uses_user_input_when_no_existing_path():
    result = FileTool().run("read", {"user_input": "帮我总结：今天完成了接口联调。"})

    assert result["content"] == "帮我总结：今天完成了接口联调。"
    assert result["source_type"] == "inline"
    assert result["source"] == "user_input"


def test_file_tool_reports_missing_named_file_instead_of_treating_request_as_content(tmp_path):
    with pytest.raises(FileNotFoundError, match="文件不存在：missing.md"):
        FileTool(project_root=tmp_path).run("read", {"user_input": "读取 missing.md 的内容"})


def test_file_tool_reads_relative_text_file_from_workspace(tmp_path):
    source = tmp_path / "README.md"
    source.write_text("这是工作区说明。", encoding="utf-8")

    result = FileTool(project_root=tmp_path).run("read", {"user_input": "读取 README.md 的内容"})

    assert result["content"] == "这是工作区说明。"
    assert result["source"] == str(source)
    assert result["workspace_root"] == str(tmp_path.resolve())


def test_file_tool_reads_common_code_file_from_workspace(tmp_path):
    source = tmp_path / "main.py"
    source.write_text("print('workspace')\n", encoding="utf-8")

    result = FileTool(project_root=tmp_path).run("read", {"user_input": "读取 main.py"})

    assert result["content"] == "print('workspace')\n"
    assert result["file_kind"] == "text"


def test_file_tool_lists_current_workspace_entries(tmp_path):
    (tmp_path / "README.md").write_text("说明", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    result = FileTool(project_root=tmp_path).run("list", {"user_input": "当前工作区有哪些文件"})

    assert result["source_type"] == "directory"
    assert result["workspace_root"] == str(tmp_path.resolve())
    assert result["entries"] == [
        {"name": "docs", "path": "docs", "type": "directory"},
        {"name": "README.md", "path": "README.md", "type": "file"},
    ]


def test_file_tool_collects_key_workspace_content_for_summary(tmp_path):
    (tmp_path / "README.md").write_text("这是一个任务 Agent 项目。", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('agent')\n", encoding="utf-8")

    result = FileTool(project_root=tmp_path).run(
        "read",
        {"user_input": "读取下这个文件夹的内容，总结一下这是在干什么，不要修改"},
    )

    assert result["source_type"] == "directory"
    assert "README.md" in result["content"]
    assert "这是一个任务 Agent 项目" in result["content"]
    assert "main.py" in result["content"]


def test_file_tool_rejects_relative_path_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "secret.md").write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="工作区之外"):
        FileTool(project_root=workspace).run("read", {"user_input": "读取 ../secret.md"})
