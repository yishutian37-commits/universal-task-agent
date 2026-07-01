from desktop.memory_compression import CompressionPolicy, estimate_tokens


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
