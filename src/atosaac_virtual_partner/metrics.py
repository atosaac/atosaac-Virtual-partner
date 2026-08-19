from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderMetrics:
    """Usage and timing values reported by one model provider."""

    provider_name: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_total_seconds: float | None = None
    load_seconds: float | None = None
    prompt_eval_seconds: float | None = None
    generation_seconds: float | None = None

    @property
    def output_tokens_per_second(self) -> float | None:
        if (
            self.output_tokens is None
            or self.generation_seconds is None
            or self.generation_seconds <= 0
        ):
            return None
        return self.output_tokens / self.generation_seconds


@dataclass(frozen=True, slots=True)
class ReplyMetrics:
    """End-to-end metrics for one successfully completed reply."""

    first_text_seconds: float
    total_seconds: float
    provider: ProviderMetrics | None = None
    local_fallback_used: bool = False


def format_reply_metrics(metrics: ReplyMetrics) -> str:
    """Format metrics without including prompts or generated text."""
    parts = [
        f"首字 {metrics.first_text_seconds:.2f}s",
        f"总耗时 {metrics.total_seconds:.2f}s",
    ]
    provider = metrics.provider
    if provider is not None:
        if provider.input_tokens is not None:
            parts.append(f"输入 {provider.input_tokens} tokens")
        if provider.output_tokens is not None:
            parts.append(f"输出 {provider.output_tokens} tokens")
        speed = provider.output_tokens_per_second
        if speed is not None:
            parts.append(f"生成 {speed:.1f} tokens/s")
    if metrics.local_fallback_used:
        parts.append("已用本地回退")
    return "[指标] " + " | ".join(parts)
