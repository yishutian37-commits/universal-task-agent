from rag.query_normalizer import expand_knowledge_query, normalize_knowledge_query


def test_normalize_knowledge_query_extracts_topic_from_common_delivery_phrases():
    cases = {
        "把知识库中 Loop 相关知识发给我": "Loop",
        "将知识库中 RAG 如何构建的部分发给我": "RAG 如何构建",
        "请介绍一下 MCP 工具的相关内容": "MCP 工具",
        "请逐字发给我知识库中 RAG 构建章节的完整原文": "RAG 构建",
    }

    for question, expected in cases.items():
        assert normalize_knowledge_query(question) == expected


def test_normalize_knowledge_query_preserves_real_knowledge_base_questions():
    assert normalize_knowledge_query("知识库是什么") == "知识库是什么"
    assert normalize_knowledge_query("如何构建知识库") == "如何构建知识库"


def test_expand_knowledge_query_adds_generic_intent_terms_without_topic_hardcoding():
    assert expand_knowledge_query("RAG 如何构建") == (
        "RAG 如何构建 基础流程 核心步骤 架构"
    )
    assert expand_knowledge_query("MCP 是什么") == "MCP 是什么 定义 核心概念"
    assert expand_knowledge_query("RAG 和 Memory 的区别") == (
        "RAG 和 Memory 的区别 对比 差异"
    )
    assert expand_knowledge_query("Loop") == "Loop"
