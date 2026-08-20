from datetime import datetime, timezone

import pytest

from atosaac_virtual_partner.tooling import (
    ToolDescriptor,
    ToolFailureCode,
    ToolGateway,
    ToolInputError,
    ToolOutput,
    ToolPermission,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    ToolUnavailableError,
)


class RecordingAdapter:
    descriptor = ToolDescriptor(
        name="weather.current",
        description="Read current weather for a configured city.",
        permission=ToolPermission.READ_ONLY,
    )

    def __init__(self, outcome=None) -> None:
        self.outcome = outcome or ToolOutput({"temperature_c": 24.0})
        self.calls: list[tuple[dict[str, object], float]] = []

    def execute(self, arguments, timeout_seconds):
        self.calls.append((dict(arguments), timeout_seconds))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_tool_request_normalizes_and_freezes_scalar_arguments() -> None:
    request = ToolRequest(
        " WEATHER.Current ",
        {" city ": "上海", "forecast_days": 1},
        timeout_seconds=3,
    )

    assert request.tool_name == "weather.current"
    assert request.arguments == {"city": "上海", "forecast_days": 1}
    assert request.timeout_seconds == 3.0
    with pytest.raises(TypeError):
        request.arguments["city"] = "北京"  # type: ignore[index]


@pytest.mark.parametrize(
    "request_factory",
    (
        lambda: ToolRequest("bad name", {}),
        lambda: ToolRequest("weather.current", {}, timeout_seconds=0),
        lambda: ToolRequest("weather.current", {"nested": {"bad": True}}),
        lambda: ToolRequest("weather.current", {"value": float("inf")}),
    ),
)
def test_tool_request_rejects_invalid_boundaries(request_factory) -> None:
    with pytest.raises(ValueError):
        request_factory()


def test_registry_rejects_duplicate_capability_names() -> None:
    adapter = RecordingAdapter()
    registry = ToolRegistry((adapter,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(RecordingAdapter())


def test_gateway_denies_unapproved_permission_without_running_adapter() -> None:
    adapter = RecordingAdapter()
    gateway = ToolGateway(ToolRegistry((adapter,)))

    result = gateway.execute(ToolRequest("weather.current", {"city": "上海"}))

    assert result.failure_code is ToolFailureCode.PERMISSION_DENIED
    assert result.succeeded is False
    assert adapter.calls == []


def test_gateway_returns_not_found_for_unregistered_capability() -> None:
    gateway = ToolGateway(
        ToolRegistry(),
        allowed_permissions=(ToolPermission.READ_ONLY,),
    )

    result = gateway.execute(ToolRequest("weather.current", {}))

    assert result.failure_code is ToolFailureCode.NOT_FOUND


def test_gateway_runs_approved_adapter_with_timeout_and_provenance() -> None:
    observed_at = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
    adapter = RecordingAdapter(
        ToolOutput(
            {"temperature_c": 24.0},
            source="example weather",
            observed_at=observed_at,
        )
    )
    times = iter((10.0, 10.25))
    gateway = ToolGateway(
        ToolRegistry((adapter,)),
        allowed_permissions=(ToolPermission.READ_ONLY,),
        clock=lambda: next(times),
    )

    result = gateway.execute(
        ToolRequest("weather.current", {"city": "上海"}, timeout_seconds=2.5)
    )

    assert result.succeeded is True
    assert result.output is not None
    assert result.output.source == "example weather"
    assert result.output.observed_at == observed_at
    assert result.elapsed_seconds == pytest.approx(0.25)
    assert adapter.calls == [({"city": "上海"}, 2.5)]


@pytest.mark.parametrize(
    ("error", "expected_code"),
    (
        (ToolInputError("private details"), ToolFailureCode.INVALID_ARGUMENTS),
        (TimeoutError("socket details"), ToolFailureCode.TIMEOUT),
        (ToolUnavailableError("provider details"), ToolFailureCode.UNAVAILABLE),
        (RuntimeError("implementation details"), ToolFailureCode.INTERNAL_ERROR),
    ),
)
def test_gateway_normalizes_adapter_failures_without_leaking_details(
    error: BaseException,
    expected_code: ToolFailureCode,
) -> None:
    adapter = RecordingAdapter(error)
    gateway = ToolGateway(
        ToolRegistry((adapter,)),
        allowed_permissions=(ToolPermission.READ_ONLY,),
    )

    result = gateway.execute(ToolRequest("weather.current", {}))

    assert result.failure_code is expected_code
    assert result.output is None
    assert "details" not in (result.message or "")


def test_tool_output_requires_timezone_aware_observation_time() -> None:
    with pytest.raises(ValueError, match="timezone"):
        ToolOutput({}, observed_at=datetime(2026, 8, 20, 8, 0))


@pytest.mark.parametrize(
    "result_factory",
    (
        lambda: ToolResult("weather.current", 0.1),
        lambda: ToolResult(
            "weather.current",
            0.1,
            output=ToolOutput({}),
            failure_code=ToolFailureCode.INTERNAL_ERROR,
        ),
        lambda: ToolResult(
            "weather.current",
            -0.1,
            output=ToolOutput({}),
        ),
    ),
)
def test_tool_result_requires_one_valid_outcome(result_factory) -> None:
    with pytest.raises(ValueError):
        result_factory()
