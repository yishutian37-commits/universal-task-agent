import pytest

from desktop.memory_compression import (
    CompressionFormatError,
    CompressionPolicy,
    default_long_term_memory,
    estimate_tokens,
    merge_long_term_memory,
    parse_compression_result,
)


def test_estimate_tokens_uses_conservative_character_ratio():
    assert estimate_tokens("abcd" * 100) == 100


def test_large_context_policy_caps_at_250k():
    policy = CompressionPolicy(context_window_tokens=400_000)

    assert policy.trigger_tokens == 250_000
    assert policy.should_compress(249_999) is False
    assert policy.should_compress(250_000) is True


def test_small_context_policy_triggers_before_model_limit():
    policy = CompressionPolicy(context_window_tokens=32_000)

    assert policy.trigger_tokens == 22_400
    assert policy.should_compress(22_399) is False
    assert policy.should_compress(22_400) is True


def test_parse_compression_result_accepts_expected_json():
    result = parse_compression_result(
        """
        {
          "short_term_summary": "用户正在改造 UTA 的记忆系统。",
          "long_term_candidates": [
            {
              "kind": "preference",
              "content": "用户明确要求使用中文回复。",
              "confidence": 0.95,
              "source_message_ids": ["msg_1"]
            }
          ],
          "open_questions": ["是否默认开启自动压缩？"]
        }
        """
    )

    assert result == {
        "short_term_summary": "用户正在改造 UTA 的记忆系统。",
        "long_term_candidates": [
            {
                "kind": "preference",
                "content": "用户明确要求使用中文回复。",
                "confidence": 0.95,
                "source_message_ids": ["msg_1"],
            }
        ],
        "open_questions": ["是否默认开启自动压缩？"],
    }


def test_parse_compression_result_rejects_unknown_memory_kind():
    with pytest.raises(CompressionFormatError, match="未知记忆类型"):
        parse_compression_result(
            {
                "short_term_summary": "摘要",
                "long_term_candidates": [
                    {
                        "kind": "random",
                        "content": "内容",
                        "confidence": 0.8,
                        "source_message_ids": ["msg_1"],
                    }
                ],
                "open_questions": [],
            }
        )


def test_parse_compression_result_rejects_non_json_text():
    with pytest.raises(CompressionFormatError, match="必须是 JSON"):
        parse_compression_result("我觉得用户比较喜欢中文。")


def test_merge_long_term_memory_adds_new_candidate():
    merged = merge_long_term_memory(
        default_long_term_memory(),
        [
            {
                "kind": "preference",
                "content": "用户明确要求使用中文回复。",
                "confidence": 0.95,
                "source_message_ids": ["msg_1"],
            }
        ],
        conversation_id="conv_20260701_120000_000000",
        now="2026-07-01T12:00:00.000000",
    )

    assert merged["version"] == 1
    assert merged["profile"]["preferences"] == ["用户明确要求使用中文回复。"]
    assert len(merged["facts"]) == 1
    assert merged["facts"][0]["kind"] == "preference"
    assert merged["facts"][0]["content"] == "用户明确要求使用中文回复。"
    assert merged["facts"][0]["source_conversation_id"] == "conv_20260701_120000_000000"
    assert merged["facts"][0]["source_message_ids"] == ["msg_1"]
    assert merged["facts"][0]["first_seen_at"] == "2026-07-01T12:00:00.000000"
    assert merged["facts"][0]["last_seen_at"] == "2026-07-01T12:00:00.000000"


def test_merge_long_term_memory_updates_existing_candidate_without_duplicate():
    memory = default_long_term_memory()
    memory["facts"].append(
        {
            "memory_id": "mem_existing",
            "kind": "preference",
            "content": "用户明确要求使用中文回复。",
            "source_conversation_id": "conv_old",
            "source_message_ids": ["msg_1"],
            "confidence": 0.7,
            "first_seen_at": "2026-06-30T12:00:00.000000",
            "last_seen_at": "2026-06-30T12:00:00.000000",
        }
    )

    merged = merge_long_term_memory(
        memory,
        [
            {
                "kind": "preference",
                "content": "用户明确要求使用中文回复。",
                "confidence": 0.95,
                "source_message_ids": ["msg_2"],
            }
        ],
        conversation_id="conv_20260701_120000_000000",
        now="2026-07-01T12:00:00.000000",
    )

    assert len(merged["facts"]) == 1
    assert merged["facts"][0]["memory_id"] == "mem_existing"
    assert merged["facts"][0]["confidence"] == 0.95
    assert merged["facts"][0]["first_seen_at"] == "2026-06-30T12:00:00.000000"
    assert merged["facts"][0]["last_seen_at"] == "2026-07-01T12:00:00.000000"
    assert merged["facts"][0]["source_message_ids"] == ["msg_1", "msg_2"]
