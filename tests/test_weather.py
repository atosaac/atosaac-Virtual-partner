from urllib.parse import parse_qs, urlparse

import pytest

from atosaac_virtual_partner.tooling import (
    ToolInputError,
    ToolPermission,
    ToolUnavailableError,
)
from atosaac_virtual_partner.weather import (
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_GEOCODING_URL,
    OpenMeteoWeatherAdapter,
)


GEOCODING_RESPONSE = {
    "results": [
        {
            "name": "上海",
            "latitude": 31.22222,
            "longitude": 121.45806,
            "admin1": "上海市",
            "country": "中国",
        }
    ]
}
FORECAST_RESPONSE = {
    "utc_offset_seconds": 28800,
    "timezone": "Asia/Shanghai",
    "current": {
        "time": "2026-08-20T10:15",
        "temperature_2m": 29.4,
        "apparent_temperature": 34.1,
        "relative_humidity_2m": 78,
        "precipitation": 0.0,
        "rain": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 10.2,
    },
    "daily": {
        "temperature_2m_max": [32.2],
        "temperature_2m_min": [25.8],
        "precipitation_probability_max": [65],
    },
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RecordingFetcher:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.responses = [GEOCODING_RESPONSE, FORECAST_RESPONSE]
        self.calls: list[tuple[str, float]] = []
        self.error: BaseException | None = None

    def __call__(self, url: str, timeout_seconds: float):
        self.calls.append((url, timeout_seconds))
        self.clock.now += 0.1
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


def build_adapter(clock: FakeClock, fetcher: RecordingFetcher, **options):
    return OpenMeteoWeatherAdapter(
        clock=clock,
        fetch_json=fetcher,
        **options,
    )


def test_weather_adapter_is_read_only_and_returns_provenance() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(clock, fetcher)

    output = adapter.execute({"city": " 上海 "}, timeout_seconds=3.0)

    assert adapter.descriptor.permission is ToolPermission.READ_ONLY
    assert output.source == "Open-Meteo Forecast API"
    assert output.observed_at is not None
    assert output.observed_at.isoformat() == "2026-08-20T10:15:00+08:00"
    assert output.data["location"] == "上海，上海市，中国"
    assert output.data["condition"] == "局部多云"
    assert output.data["temperature_c"] == 29.4
    assert output.data["today_precipitation_probability_max_percent"] == 65.0
    assert output.data["from_cache"] is False
    assert output.data["is_stale"] is False

    geocoding_url, geocoding_timeout = fetcher.calls[0]
    assert geocoding_url.startswith(OPEN_METEO_GEOCODING_URL)
    geocoding_query = parse_qs(urlparse(geocoding_url).query)
    assert geocoding_query == {
        "name": ["上海"],
        "count": ["1"],
        "language": ["zh"],
        "format": ["json"],
    }
    assert geocoding_timeout == pytest.approx(3.0)

    forecast_url, forecast_timeout = fetcher.calls[1]
    assert forecast_url.startswith(OPEN_METEO_FORECAST_URL)
    forecast_query = parse_qs(urlparse(forecast_url).query)
    assert forecast_query["latitude"] == ["31.22222"]
    assert forecast_query["longitude"] == ["121.45806"]
    assert forecast_query["timezone"] == ["auto"]
    assert forecast_query["forecast_days"] == ["1"]
    assert forecast_timeout == pytest.approx(2.9)


def test_weather_adapter_uses_fresh_cache_without_network() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(clock, fetcher, cache_seconds=600)
    first = adapter.execute({"city": "上海"}, timeout_seconds=3.0)
    clock.now = 300

    second = adapter.execute({"city": "上海"}, timeout_seconds=3.0)

    assert len(fetcher.calls) == 2
    assert second.observed_at == first.observed_at
    assert second.data["from_cache"] is True
    assert second.data["is_stale"] is False


def test_weather_refresh_reuses_resolved_location() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(clock, fetcher, cache_seconds=60)
    adapter.execute({"city": "上海"}, timeout_seconds=3.0)
    clock.now = 120
    fetcher.responses.append(FORECAST_RESPONSE)

    refreshed = adapter.execute({"city": "上海"}, timeout_seconds=3.0)

    assert len(fetcher.calls) == 3
    assert fetcher.calls[-1][0].startswith(OPEN_METEO_FORECAST_URL)
    assert refreshed.data["from_cache"] is False


def test_weather_adapter_falls_back_to_bounded_stale_cache() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(
        clock,
        fetcher,
        cache_seconds=60,
        max_stale_seconds=600,
    )
    first = adapter.execute({"city": "上海"}, timeout_seconds=3.0)
    clock.now = 120
    fetcher.error = ToolUnavailableError("offline")

    second = adapter.execute({"city": "上海"}, timeout_seconds=3.0)

    assert second.observed_at == first.observed_at
    assert second.data["from_cache"] is True
    assert second.data["is_stale"] is True


def test_weather_adapter_does_not_serve_cache_beyond_stale_limit() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(
        clock,
        fetcher,
        cache_seconds=60,
        max_stale_seconds=600,
    )
    adapter.execute({"city": "上海"}, timeout_seconds=3.0)
    clock.now = 601
    fetcher.error = TimeoutError("offline")

    with pytest.raises(TimeoutError):
        adapter.execute({"city": "上海"}, timeout_seconds=3.0)


@pytest.mark.parametrize(
    "arguments",
    (
        {},
        {"city": 123},
        {"city": "上"},
        {"city": "上海", "url": "https://example.com"},
    ),
)
def test_weather_adapter_rejects_invalid_or_extra_arguments(arguments) -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    adapter = build_adapter(clock, fetcher)

    with pytest.raises(ToolInputError):
        adapter.execute(arguments, timeout_seconds=3.0)

    assert fetcher.calls == []


def test_weather_adapter_reports_unknown_city_as_invalid_input() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    fetcher.responses = [{"results": []}]
    adapter = build_adapter(clock, fetcher)

    with pytest.raises(ToolInputError, match="not found"):
        adapter.execute({"city": "不存在的测试城市"}, timeout_seconds=3.0)


def test_weather_adapter_rejects_malformed_provider_data() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)
    fetcher.responses = [GEOCODING_RESPONSE, {"current": {}, "daily": {}}]
    adapter = build_adapter(clock, fetcher)

    with pytest.raises(RuntimeError, match="Open-Meteo field"):
        adapter.execute({"city": "上海"}, timeout_seconds=3.0)


def test_weather_adapter_validates_cache_configuration() -> None:
    clock = FakeClock()
    fetcher = RecordingFetcher(clock)

    with pytest.raises(ValueError, match="less than"):
        build_adapter(
            clock,
            fetcher,
            cache_seconds=600,
            max_stale_seconds=60,
        )
