import pytest

from desktop.chat_router import chat_route_kind, direct_chat_response


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("你好", "可以直接把任务发给我"),
        ("你是谁", "我是 UTA"),
        ("你能干什么", "文本总结"),
        ("有哪些功能", "复杂任务拆解"),
        ("这个应用怎么用", "发送任务"),
        ("桌面端能看到哪些状态", "执行步骤"),
    ],
)
def test_direct_chat_response_handles_common_chat_modes(message, expected):
    response = direct_chat_response(message)

    assert response is not None
    assert expected in response.content


@pytest.mark.parametrize(
    "message",
    [
        "帮我总结一段文本：今天开会讨论了库存问题。",
        "分析 examples/orders.csv",
        "调研包头今日天气状况",
        "帮我执行复杂任务：[1]总结文章 [2]提炼结论",
        "阅读当前项目代码，说明任务链路",
    ],
)
def test_direct_chat_response_does_not_steal_task_messages(message):
    assert direct_chat_response(message) is None


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


def test_chat_route_kind_detects_direct_help():
    assert chat_route_kind("这个应用怎么用") == "direct"
