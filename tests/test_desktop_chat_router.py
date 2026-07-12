import pytest

from desktop.chat_router import chat_route_kind


@pytest.mark.parametrize(
    "message",
    [
        "我想学习 AI，你建议从哪里开始？",
        "这个方向你怎么看",
        "帮我想想思路",
    ],
)
def test_chat_route_kind_detects_general_chat(message):
    assert chat_route_kind(message) == "chat"


@pytest.mark.parametrize(
    "message",
    [
        "帮我总结一段文本：今天开会讨论了库存问题。",
        "帮我写一个当前应用介绍",
        "请分析 examples/orders.csv",
        "帮我做 GEO 分析：行业是本地装修",
    ],
)
def test_chat_route_kind_detects_tasks(message):
    assert chat_route_kind(message) == "task"


@pytest.mark.parametrize(
    "message",
    [
        "当前工作区有哪些文件",
        "列出工作区文件",
        "读取 README.md 的内容",
        "读取下这个文件夹的内容，总结一下这是在干什么，不要修改",
    ],
)
def test_chat_route_kind_detects_workspace_file_tasks(message):
    assert chat_route_kind(message) == "task"


def test_chat_route_kind_detects_direct_help():
    assert chat_route_kind("这个应用怎么用") == "direct"
