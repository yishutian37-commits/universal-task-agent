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
