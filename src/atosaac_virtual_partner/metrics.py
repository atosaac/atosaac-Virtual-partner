import math
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
class ToolMetrics:
    """Record content-free timing and cache state for one tool call."""

    tool_name: str
    elapsed_seconds: float
    succeeded: bool
    failure_code: str | None = None
    from_cache: bool = False
    stale: bool = False

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("Tool metric name cannot be empty")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("Tool metric elapsed time must be non-negative")
        if self.succeeded == (self.failure_code is not None):
            raise ValueError("Tool metric success and failure state is inconsistent")
        if not self.succeeded and (self.from_cache or self.stale):
            raise ValueError("Failed tool metrics cannot report cache success")
        if self.stale and not self.from_cache:
            raise ValueError("Stale tool metrics must come from cache")


@dataclass(frozen=True, slots=True)
class ReplyMetrics:
    """End-to-end metrics for one successfully completed reply."""

    first_text_seconds: float
    total_seconds: float
    provider: ProviderMetrics | None = None
    tool: ToolMetrics | None = None
    local_fallback_used: bool = False
    grounding_risks: tuple[str, ...] = ()
    memory_created: int = 0
    memory_updated: int = 0
    memory_read_failed: bool = False
    memory_capture_failed: bool = False


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
    tool = metrics.tool
    if tool is not None:
        if tool.succeeded:
            cache_label = ""
            if tool.stale:
                cache_label = " 过期缓存"
            elif tool.from_cache:
                cache_label = " 缓存"
            parts.append(
                f"工具 {tool.tool_name} {tool.elapsed_seconds:.2f}s{cache_label}"
            )
        else:
            parts.append(
                f"工具 {tool.tool_name} 失败 {tool.failure_code or 'unknown'}"
            )
    if metrics.local_fallback_used:
        parts.append("已用本地回退")
    if metrics.grounding_risks:
        risk_labels = {
            "unsupported_memory": "记忆",
            "unsupported_perception": "感知",
            "unsupported_physical_state": "身体状态",
            "unsupported_self_history": "自身经历",
        }
        labels = (
            risk_labels.get(risk, risk) for risk in metrics.grounding_risks
        )
        parts.append("事实风险 " + "、".join(labels))
    if metrics.memory_created:
        parts.append(f"记忆新增 {metrics.memory_created}")
    if metrics.memory_updated:
        parts.append(f"记忆更新 {metrics.memory_updated}")
    if metrics.memory_read_failed:
        parts.append("记忆读取已回退")
    if metrics.memory_capture_failed:
        parts.append("记忆保存失败")
    return "[指标] " + " | ".join(parts)
