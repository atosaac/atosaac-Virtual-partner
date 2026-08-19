from atosaac_virtual_partner.metrics import (
    ProviderMetrics,
    ReplyMetrics,
    format_reply_metrics,
)


def test_provider_metrics_calculates_output_speed() -> None:
    metrics = ProviderMetrics(
        provider_name="test",
        output_tokens=20,
        generation_seconds=0.5,
    )

    assert metrics.output_tokens_per_second == 40.0


def test_format_reply_metrics_contains_only_safe_aggregate_values() -> None:
    metrics = ReplyMetrics(
        first_text_seconds=0.42,
        total_seconds=1.5,
        provider=ProviderMetrics(
            provider_name="ollama",
            model="test-model",
            input_tokens=100,
            output_tokens=20,
            generation_seconds=0.5,
        ),
    )

    summary = format_reply_metrics(metrics)

    assert summary == (
        "[指标] 首字 0.42s | 总耗时 1.50s | 输入 100 tokens | "
        "输出 20 tokens | 生成 40.0 tokens/s"
    )
    assert "prompt" not in summary
    assert "message" not in summary


def test_format_reply_metrics_reports_local_fallback_without_content() -> None:
    summary = format_reply_metrics(
        ReplyMetrics(
            first_text_seconds=0.5,
            total_seconds=0.5,
            local_fallback_used=True,
        )
    )

    assert summary == "[指标] 首字 0.50s | 总耗时 0.50s | 已用本地回退"


def test_format_reply_metrics_reports_content_free_grounding_risks() -> None:
    summary = format_reply_metrics(
        ReplyMetrics(
            first_text_seconds=0.3,
            total_seconds=0.8,
            grounding_risks=(
                "unsupported_memory",
                "unsupported_perception",
                "unsupported_self_history",
            ),
        )
    )

    assert summary == (
        "[指标] 首字 0.30s | 总耗时 0.80s | 事实风险 记忆、感知、自身经历"
    )
