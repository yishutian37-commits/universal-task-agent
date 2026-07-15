from pathlib import Path

import pytest

from tools.authorization import AuthorizationDecision


class FakeAuthorizationManager:
    def __init__(self, decision):
        self.decision = decision
        self.requests = []

    def request(self, operation, timeout=None):
        self.requests.append((operation, timeout))
        return self.decision


class FakeShellRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, cwd, timeout):
        self.calls.append((command, cwd, timeout))

        class Result:
            returncode = 0
            stdout = "hello\n"
            stderr = ""

        return Result()


def approved_decision():
    return AuthorizationDecision(
        request_id="auth_test",
        approved=True,
        status="approved",
        approved_by="tester",
    )


def rejected_decision():
    return AuthorizationDecision(
        request_id="auth_test",
        approved=False,
        status="rejected",
        reason="用户拒绝",
    )


def test_shell_tool_requires_authorization_before_execution(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    runner = FakeShellRunner()
    auth = FakeAuthorizationManager(rejected_decision())
    tool = ShellLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=runner,
    )

    with pytest.raises(PermissionError, match="用户拒绝"):
        tool.invoke({"command": "echo hello", "cwd": str(tmp_path)})

    assert runner.calls == []
    assert auth.requests[0][0]["tool_name"] == "langchain_shell_tool"
    assert auth.requests[0][0]["command"] == "echo hello"


def test_shell_tool_executes_after_authorization(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    runner = FakeShellRunner()
    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=runner,
    )

    result = tool.invoke({"command": "echo hello", "cwd": str(tmp_path)})

    assert runner.calls == [("echo hello", str(tmp_path), 10)]
    assert result["returncode"] == 0
    assert result["stdout"] == "hello\n"
    assert result["authorized_by"] == "tester"


def test_shell_tool_uses_current_input_instead_of_older_conversation_command(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    runner = FakeShellRunner()
    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=runner,
    )
    query = "\n\n".join(
        [
            "以下是同一对话前文。\n- 用户：执行 shell 命令 echo old",
            "当前用户输入：\n执行 shell 命令 echo current",
        ]
    )

    tool.invoke({"query": query})

    assert runner.calls == [("echo current", str(tmp_path), 10)]


def test_shell_tool_rejects_dangerous_command(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=FakeShellRunner(),
    )

    with pytest.raises(ValueError, match="禁止执行高风险命令"):
        tool.invoke({"command": "sudo rm -rf /", "cwd": str(tmp_path)})


def test_shell_tool_rejects_cwd_outside_allowed_roots(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=FakeShellRunner(),
    )

    with pytest.raises(ValueError, match="不允许访问授权目录之外"):
        tool.invoke({"command": "echo hello", "cwd": str(outside)})


def test_shell_tool_rejects_path_argument_outside_allowed_roots(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    outside = tmp_path.parent / "outside.txt"
    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=FakeShellRunner(),
    )

    with pytest.raises(ValueError, match="不允许访问授权目录之外"):
        tool.invoke({"command": f"touch {outside}", "cwd": str(tmp_path)})


def test_shell_tool_rejects_shell_control_operators(tmp_path):
    from tools.langchain_common_tools import ShellLangChainTool

    tool = ShellLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        command_runner=FakeShellRunner(),
    )

    with pytest.raises(ValueError, match="不支持 Shell 控制符"):
        tool.invoke({"command": "echo hello > outside.txt", "cwd": str(tmp_path)})


def test_directory_create_tool_requires_authorization(tmp_path):
    from tools.langchain_common_tools import DirectoryCreateLangChainTool

    target = tmp_path / "测试"
    auth = FakeAuthorizationManager(rejected_decision())
    tool = DirectoryCreateLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
        desktop_root=tmp_path,
    )

    with pytest.raises(PermissionError, match="用户拒绝"):
        tool.invoke({"query": "帮我在桌面创建一个名叫测试的文件夹"})

    assert not target.exists()
    assert auth.requests[0][0]["tool_name"] == "langchain_directory_create_tool"
    assert auth.requests[0][0]["path"] == str(target)


def test_directory_create_tool_creates_desktop_folder_after_authorization(tmp_path):
    from tools.langchain_common_tools import DirectoryCreateLangChainTool

    tool = DirectoryCreateLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        desktop_root=tmp_path,
    )

    result = tool.invoke({"query": "帮我在桌面创建一个名叫测试的文件夹"})

    assert (tmp_path / "测试").is_dir()
    assert result["path"] == str(tmp_path / "测试")
    assert result["created"] is True
    assert result["authorized_by"] == "tester"


def test_directory_create_tool_uses_current_input_instead_of_older_conversation_request(tmp_path):
    from tools.langchain_common_tools import DirectoryCreateLangChainTool

    tool = DirectoryCreateLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        desktop_root=tmp_path,
    )
    query = "\n\n".join(
        [
            "以下是同一对话前文，仅用于理解指代。\n- 用户：帮我在桌面创建一个叫一个的文件夹",
            "当前用户输入：\n帮我在桌面创建一个叫测试的文件夹",
        ]
    )

    result = tool.invoke({"query": query})

    assert result["path"] == str(tmp_path / "测试")
    assert (tmp_path / "测试").is_dir()
    assert not (tmp_path / "一个").exists()


def test_directory_create_tool_creates_named_folder_in_current_workspace(tmp_path):
    from tools.langchain_common_tools import DirectoryCreateLangChainTool

    tool = DirectoryCreateLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        desktop_root=tmp_path / "desktop",
    )

    result = tool.invoke({"query": "在当前工作区创建一个叫测试的文件夹"})

    assert result["path"] == str(tmp_path / "测试")
    assert (tmp_path / "测试").is_dir()


def test_file_write_tool_accepts_path_and_content_from_user_supplement(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    tool = FileWriteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )
    output_path = tmp_path / "note.txt"
    query = "\n\n".join(
        [
            "当前用户输入：\n创建文件",
            f"用户补充信息：\n文件路径是 {output_path}，内容是 hello",
        ]
    )

    result = tool.invoke({"query": query})

    assert result["path"] == str(output_path)
    assert output_path.read_text(encoding="utf-8") == "hello"


def test_directory_create_tool_rejects_target_outside_allowed_roots(tmp_path):
    from tools.langchain_common_tools import DirectoryCreateLangChainTool

    tool = DirectoryCreateLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(ValueError, match="不允许访问授权目录之外"):
        tool.invoke({"path": str(tmp_path.parent / "outside")})


def test_file_write_tool_requires_authorization_before_writing(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    target = tmp_path / "note.txt"
    auth = FakeAuthorizationManager(rejected_decision())
    tool = FileWriteLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(PermissionError, match="用户拒绝"):
        tool.invoke({"path": str(target), "content": "hello"})

    assert not target.exists()
    assert auth.requests[0][0]["tool_name"] == "langchain_file_write_tool"
    assert auth.requests[0][0]["path"] == str(target)


def test_file_write_tool_writes_after_authorization(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    target = tmp_path / "note.txt"
    tool = FileWriteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    result = tool.invoke({"path": str(target), "content": "hello", "mode": "create"})

    assert target.read_text(encoding="utf-8") == "hello"
    assert result["path"] == str(target)
    assert result["mode"] == "create"
    assert result["bytes_written"] == 5


def test_file_write_tool_extracts_path_and_content_from_query(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    target = tmp_path / "note.txt"
    tool = FileWriteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    result = tool.invoke({"query": f"写入文件 {target} 内容 hello"})

    assert target.read_text(encoding="utf-8") == "hello"
    assert result["path"] == str(target)


def test_file_write_tool_rejects_outside_allowed_roots(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    tool = FileWriteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(ValueError, match="不允许访问授权目录之外"):
        tool.invoke({"path": str(Path("/tmp/outside.txt")), "content": "bad"})


def test_file_write_tool_rejects_overwrite_in_create_mode(tmp_path):
    from tools.langchain_common_tools import FileWriteLangChainTool

    target = tmp_path / "note.txt"
    target.write_text("old", encoding="utf-8")
    tool = FileWriteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(FileExistsError, match="文件已存在"):
        tool.invoke({"path": str(target), "content": "new", "mode": "create"})


def test_python_repl_tool_requires_authorization_before_execution(tmp_path):
    from tools.langchain_common_tools import PythonReplLangChainTool

    auth = FakeAuthorizationManager(rejected_decision())
    tool = PythonReplLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(PermissionError, match="用户拒绝"):
        tool.invoke({"code": "result = 1 + 2"})

    assert auth.requests[0][0]["tool_name"] == "langchain_python_repl_tool"
    assert auth.requests[0][0]["code"] == "result = 1 + 2"


def test_python_repl_tool_executes_after_authorization(tmp_path):
    from tools.langchain_common_tools import PythonReplLangChainTool

    tool = PythonReplLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )

    result = tool.invoke({"code": "print('hello')\nresult = sum([1, 2, 3])"})

    assert result["stdout"] == "hello\n"
    assert result["result_repr"] == "6"
    assert result["authorized_by"] == "tester"


def test_python_repl_tool_uses_current_input_instead_of_older_conversation_code(tmp_path):
    from tools.langchain_common_tools import PythonReplLangChainTool

    tool = PythonReplLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
    )
    query = "\n\n".join(
        [
            "以下是同一对话前文。\n- 用户：运行 Python 代码 result = 1",
            "当前用户输入：\n运行 Python 代码 result = 2",
        ]
    )

    result = tool.invoke({"query": query})

    assert result["result_repr"] == "2"


def test_python_repl_tool_rejects_forbidden_import_before_authorization(tmp_path):
    from tools.langchain_common_tools import PythonReplLangChainTool

    auth = FakeAuthorizationManager(approved_decision())
    tool = PythonReplLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
    )

    with pytest.raises(ValueError, match="禁止导入高风险模块"):
        tool.invoke({"code": "import os\nresult = os.getcwd()"})

    assert auth.requests == []


def test_file_delete_tool_requires_authorization_before_moving_to_trash(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")
    trash = tmp_path / "trash"
    auth = FakeAuthorizationManager(rejected_decision())
    tool = FileDeleteLangChainTool(
        authorization_manager=auth,
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=trash,
    )

    with pytest.raises(PermissionError, match="用户拒绝"):
        tool.invoke({"path": str(target)})

    assert target.exists()
    assert not trash.exists()
    assert auth.requests[0][0]["tool_name"] == "langchain_file_delete_tool"
    assert auth.requests[0][0]["path"] == str(target)


def test_file_delete_tool_moves_file_to_trash_after_authorization(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")
    trash = tmp_path / "trash"
    tool = FileDeleteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=trash,
    )

    result = tool.invoke({"path": str(target)})

    assert not target.exists()
    trashed_path = Path(result["trash_path"])
    assert trashed_path.exists()
    assert trashed_path.read_text(encoding="utf-8") == "old"
    assert trash in trashed_path.parents
    assert result["authorized_by"] == "tester"


def test_file_delete_tool_extracts_local_file_path_from_query(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")
    trash = tmp_path / "trash"
    tool = FileDeleteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=trash,
    )

    result = tool.invoke({"query": f"删除本地文件 {target}"})

    assert not target.exists()
    assert Path(result["trash_path"]).read_text(encoding="utf-8") == "old"


def test_file_delete_tool_uses_current_input_instead_of_older_conversation_path(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    old_target = tmp_path / "old.txt"
    current_target = tmp_path / "current.txt"
    old_target.write_text("old", encoding="utf-8")
    current_target.write_text("current", encoding="utf-8")
    tool = FileDeleteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=tmp_path / "trash",
    )
    query = "\n\n".join(
        [
            f"以下是同一对话前文。\n- 用户：删除文件 {old_target}",
            f"当前用户输入：\n删除文件 {current_target}",
        ]
    )

    result = tool.invoke({"query": query})

    assert old_target.read_text(encoding="utf-8") == "old"
    assert not current_target.exists()
    assert Path(result["trash_path"]).read_text(encoding="utf-8") == "current"


def test_file_delete_tool_rejects_deleting_allowed_root(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    tool = FileDeleteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=tmp_path / "trash",
    )

    with pytest.raises(ValueError, match="禁止删除授权根目录"):
        tool.invoke({"path": str(tmp_path)})


def test_file_delete_tool_rejects_git_directory(tmp_path):
    from tools.langchain_common_tools import FileDeleteLangChainTool

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    tool = FileDeleteLangChainTool(
        authorization_manager=FakeAuthorizationManager(approved_decision()),
        enabled=True,
        allowed_roots=[tmp_path],
        trash_root=tmp_path / "trash",
    )

    with pytest.raises(ValueError, match="禁止删除 .git"):
        tool.invoke({"path": str(git_dir)})
