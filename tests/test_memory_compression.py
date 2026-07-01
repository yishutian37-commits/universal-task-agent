import pytest

from desktop.memory_compression import (
    CompressionFormatError,
    CompressionPolicy,
    estimate_tokens,
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
