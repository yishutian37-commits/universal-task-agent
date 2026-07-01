from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    return max(1, (len(str(text or "")) + 3) // 4)


@dataclass(frozen=True)
class CompressionPolicy:
    context_window_tokens: int = 400_000
    trigger_ratio: float = 0.70
    trigger_cap_tokens: int = 250_000
    target_recent_messages: int = 12

    @property
    def trigger_tokens(self) -> int:
        return int(min(self.trigger_cap_tokens, self.context_window_tokens * self.trigger_ratio))

    def should_compress(self, token_estimate: int) -> bool:
        return int(token_estimate) >= self.trigger_tokens
