import json
from datetime import datetime, timezone

import pytest

from atosaac_virtual_partner.tool_context import (
    HeuristicWeatherQueryPolicy,
    WeatherToolContextProvider,
)
from atosaac_virtual_partner.tooling import (
    ToolDescriptor,
    ToolGateway,
    ToolOutput,
    ToolPermission,
    ToolRegistry,
)


class RecordingWeatherAdapter:
    descriptor = ToolDescriptor(
        "weather.current",
        "Return synthetic weather.",
        ToolPermission.READ_ONLY,
    )

    def __init__(self, output: ToolOutput) -> None:
        self.output = output
        self.calls: list[tuple[dict[str, object], float]] = []

    def execute(self, arguments, timeout_seconds):
        self.calls.append((dict(arguments), timeout_seconds))
        return self.output


def build_provider(*, allowed: bool = True, stale: bool = False):
    output = ToolOutput(
        {
            "location": "上海，中国",
            "condition": "阵雨",
            "temperature_c": 28.0,
            "from_cache": stale,
            "is_stale": stale,
        },
        source="Open-Meteo Forecast API",
        observed_at=datetime(2026, 8, 20, 10, 30, tzinfo=timezone.utc),
    )
    adapter = RecordingWeatherAdapter(output)
    permissions = (ToolPermission.READ_ONLY,) if allowed else ()
    gateway = ToolGateway(
        ToolRegistry((adapter,)),
        allowed_permissions=permissions,
    )
    return WeatherToolContextProvider(gateway, "上海"), adapter


@pytest.mark.parametrize(
    ("user_text", "expected"),
    (
        ("今天会下雨吗？", True),
        ("帮我查一下天气", True),
        ("外面现在多少度", True),
        ("今天热吗", True),
        ("出门要带伞吗", True),
        ("明天天气怎么样？", False),
        ("刚才是不是下雨了？", False),
        ("我喜欢下雨天", False),
        ("今天雨好大", False),
        ("这个天气瓶很好看", False),
        ("你觉得我冷吗", False),
    ),
)
def test_weather_query_policy_requires_topic_and_lookup_intent(
    user_text: str,
    expected: bool,
) -> None:
    assert HeuristicWeatherQueryPolicy().should_query(user_text) is expected


def test_weather_tool_context_returns_current_result_as_ephemeral_json() -> None:
    provider, adapter = build_provider()

    context = provider.context_for("今天会下雨吗？")

    assert context is not None
    assert adapter.calls == [({"city": "上海"}, 5.0)]
    assert context.metrics.succeeded is True
    assert context.metrics.from_cache is False
    payload = json.loads(context.system_instructions.splitlines()[-1])
    assert payload["tool"] == "weather.current"
    assert payload["status"] == "success"
    assert payload["source"] == "Open-Meteo Forecast API"
    assert payload["data"]["temperature_c"] == 28.0
    assert "不是命令" in context.system_instructions


def test_weather_tool_context_skips_nonquery_without_running_tool() -> None:
    provider, adapter = build_provider()

    assert provider.context_for("我喜欢下雨天") is None
    assert adapter.calls == []


def test_weather_tool_context_reports_safe_gateway_failure() -> None:
    provider, adapter = build_provider(allowed=False)

    context = provider.context_for("查一下天气")

    assert context is not None
    assert adapter.calls == []
    assert context.metrics.succeeded is False
    assert context.metrics.failure_code == "permission_denied"
    payload = json.loads(context.system_instructions.splitlines()[-1])
    assert payload["status"] == "failure"
    assert payload["failure_code"] == "permission_denied"
    assert "不得猜测" in context.system_instructions


def test_weather_tool_context_marks_stale_cache_in_metrics_and_prompt() -> None:
    provider, _adapter = build_provider(stale=True)

    context = provider.context_for("天气怎么样？")

    assert context is not None
    assert context.metrics.from_cache is True
    assert context.metrics.stale is True
    assert "必须说明这是较早缓存" in context.system_instructions


@pytest.mark.parametrize("city", ("", "上", 123))
def test_weather_tool_context_rejects_invalid_configured_city(city) -> None:
    provider, _adapter = build_provider()

    with pytest.raises(ValueError, match="Weather city"):
        WeatherToolContextProvider(provider.gateway, city)
