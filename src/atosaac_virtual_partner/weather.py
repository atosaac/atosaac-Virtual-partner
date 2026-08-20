"""Read-only Open-Meteo weather adapter with bounded in-memory caching."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, TypeAlias
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .tooling import (
    ToolDescriptor,
    ToolInputError,
    ToolOutput,
    ToolPermission,
    ToolScalar,
    ToolUnavailableError,
)


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_SOURCE = "Open-Meteo Forecast API"
DEFAULT_WEATHER_CACHE_SECONDS = 600.0
DEFAULT_WEATHER_MAX_STALE_SECONDS = 21_600.0
DEFAULT_WEATHER_CACHE_ENTRIES = 32
MAX_WEATHER_RESPONSE_BYTES = 1_000_000
MAX_CITY_CHARACTERS = 100

JsonValue: TypeAlias = dict[str, Any]
JsonFetcher: TypeAlias = Callable[[str, float], JsonValue]
MonotonicClock: TypeAlias = Callable[[], float]


def _default_json_fetch(url: str, timeout_seconds: float) -> JsonValue:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "atosaac-virtual-partner/0.2",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read(MAX_WEATHER_RESPONSE_BYTES + 1)
    except TimeoutError:
        raise
    except (HTTPError, URLError, OSError) as exc:
        raise ToolUnavailableError("Open-Meteo request failed") from exc
    if len(payload) > MAX_WEATHER_RESPONSE_BYTES:
        raise ToolUnavailableError("Open-Meteo response is too large")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolUnavailableError("Open-Meteo returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ToolUnavailableError("Open-Meteo returned an invalid object")
    return parsed


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    return value


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    return value.strip()


def _require_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    number = float(value)
    if not math.isfinite(number):
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    return number


def _require_integer(value: object, field: str) -> int:
    number = _require_number(value, field)
    if not number.is_integer():
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    return int(number)


def _first_number(value: object, field: str) -> float:
    if not isinstance(value, list) or not value:
        raise ToolUnavailableError(f"Open-Meteo field is invalid: {field}")
    return _require_number(value[0], field)


def _condition_zh(weather_code: int) -> str:
    if weather_code == 0:
        return "晴"
    if weather_code == 1:
        return "大致晴朗"
    if weather_code == 2:
        return "局部多云"
    if weather_code == 3:
        return "阴"
    if weather_code in {45, 48}:
        return "雾"
    if weather_code in {51, 53, 55}:
        return "毛毛雨"
    if weather_code in {56, 57}:
        return "冻毛毛雨"
    if weather_code in {61, 63, 65}:
        return "雨"
    if weather_code in {66, 67}:
        return "冻雨"
    if weather_code in {71, 73, 75, 77}:
        return "雪"
    if weather_code in {80, 81, 82}:
        return "阵雨"
    if weather_code in {85, 86}:
        return "阵雪"
    if weather_code == 95:
        return "雷暴"
    if weather_code in {96, 99}:
        return "雷暴伴冰雹"
    return "未知天气"


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    output: ToolOutput
    fetched_at: float
    location: Mapping[str, Any]


class OpenMeteoWeatherAdapter:
    """Resolve a city and return current plus same-day weather data."""

    descriptor = ToolDescriptor(
        name="weather.current",
        description="查询指定城市的当前天气与当天概况。",
        permission=ToolPermission.READ_ONLY,
    )

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher = _default_json_fetch,
        clock: MonotonicClock = perf_counter,
        cache_seconds: float = DEFAULT_WEATHER_CACHE_SECONDS,
        max_stale_seconds: float = DEFAULT_WEATHER_MAX_STALE_SECONDS,
        max_cache_entries: int = DEFAULT_WEATHER_CACHE_ENTRIES,
    ) -> None:
        if not callable(fetch_json) or not callable(clock):
            raise ValueError("Weather fetcher and clock must be callable")
        for name, value in (
            ("cache_seconds", cache_seconds),
            ("max_stale_seconds", max_stale_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be a non-negative finite number")
        if max_stale_seconds < cache_seconds:
            raise ValueError("max_stale_seconds cannot be less than cache_seconds")
        if (
            isinstance(max_cache_entries, bool)
            or not isinstance(max_cache_entries, int)
            or max_cache_entries <= 0
        ):
            raise ValueError("max_cache_entries must be a positive integer")
        self._fetch_json = fetch_json
        self._clock = clock
        self._cache_seconds = float(cache_seconds)
        self._max_stale_seconds = float(max_stale_seconds)
        self._max_cache_entries = max_cache_entries
        self._cache: dict[str, _CacheEntry] = {}

    def execute(
        self,
        arguments: Mapping[str, ToolScalar],
        timeout_seconds: float,
    ) -> ToolOutput:
        if set(arguments) != {"city"}:
            raise ToolInputError("weather.current requires only city")
        city_value = arguments["city"]
        if not isinstance(city_value, str):
            raise ToolInputError("city must be text")
        city = " ".join(city_value.split())
        if len(city) < 2 or len(city) > MAX_CITY_CHARACTERS:
            raise ToolInputError("city length is invalid")

        cache_key = city.casefold()
        started_at = self._clock()
        cached = self._cache.get(cache_key)
        if cached is not None:
            age = max(0.0, started_at - cached.fetched_at)
            if age <= self._cache_seconds:
                return self._with_cache_state(cached.output, stale=False)

        deadline = started_at + timeout_seconds
        try:
            location = (
                cached.location
                if cached is not None
                else self._resolve_location(city, deadline)
            )
            output = self._fetch_weather(location, deadline)
        except (TimeoutError, ToolUnavailableError):
            if cached is not None:
                age = max(0.0, self._clock() - cached.fetched_at)
                if age <= self._max_stale_seconds:
                    return self._with_cache_state(cached.output, stale=True)
            raise

        self._store_cache(cache_key, output, location, self._clock())
        return output

    def _resolve_location(self, city: str, deadline: float) -> Mapping[str, Any]:
        query = urlencode(
            {
                "name": city,
                "count": 1,
                "language": "zh",
                "format": "json",
            }
        )
        payload = self._fetch_json(
            f"{OPEN_METEO_GEOCODING_URL}?{query}",
            self._remaining(deadline),
        )
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise ToolInputError("city was not found")
        return _require_mapping(results[0], "results[0]")

    def _fetch_weather(
        self,
        location: Mapping[str, Any],
        deadline: float,
    ) -> ToolOutput:
        latitude = _require_number(location.get("latitude"), "latitude")
        longitude = _require_number(location.get("longitude"), "longitude")
        query = urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,apparent_temperature,"
                    "relative_humidity_2m,precipitation,rain,weather_code,"
                    "wind_speed_10m"
                ),
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "timezone": "auto",
                "forecast_days": 1,
            }
        )
        payload = self._fetch_json(
            f"{OPEN_METEO_FORECAST_URL}?{query}",
            self._remaining(deadline),
        )
        return self._parse_weather(location, payload)

    @staticmethod
    def _parse_weather(
        location: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> ToolOutput:
        current = _require_mapping(payload.get("current"), "current")
        daily = _require_mapping(payload.get("daily"), "daily")
        timezone_name = _require_text(payload.get("timezone"), "timezone")
        weather_code = _require_integer(current.get("weather_code"), "weather_code")
        observed_at = OpenMeteoWeatherAdapter._parse_observation_time(
            _require_text(current.get("time"), "current.time"),
            timezone_name,
            payload.get("utc_offset_seconds"),
        )

        location_parts = [_require_text(location.get("name"), "location.name")]
        for field in ("admin1", "country"):
            value = location.get(field)
            if isinstance(value, str) and value.strip() not in location_parts:
                location_parts.append(value.strip())

        data: dict[str, ToolScalar] = {
            "location": "，".join(location_parts),
            "timezone": timezone_name,
            "condition": _condition_zh(weather_code),
            "weather_code": weather_code,
            "temperature_c": _require_number(
                current.get("temperature_2m"),
                "temperature_2m",
            ),
            "apparent_temperature_c": _require_number(
                current.get("apparent_temperature"),
                "apparent_temperature",
            ),
            "relative_humidity_percent": _require_number(
                current.get("relative_humidity_2m"),
                "relative_humidity_2m",
            ),
            "precipitation_mm": _require_number(
                current.get("precipitation"),
                "precipitation",
            ),
            "rain_mm": _require_number(current.get("rain"), "rain"),
            "wind_speed_kmh": _require_number(
                current.get("wind_speed_10m"),
                "wind_speed_10m",
            ),
            "today_temperature_max_c": _first_number(
                daily.get("temperature_2m_max"),
                "daily.temperature_2m_max",
            ),
            "today_temperature_min_c": _first_number(
                daily.get("temperature_2m_min"),
                "daily.temperature_2m_min",
            ),
            "today_precipitation_probability_max_percent": _first_number(
                daily.get("precipitation_probability_max"),
                "daily.precipitation_probability_max",
            ),
            "from_cache": False,
            "is_stale": False,
        }
        return ToolOutput(
            data,
            source=OPEN_METEO_SOURCE,
            observed_at=observed_at,
        )

    @staticmethod
    def _parse_observation_time(
        value: str,
        timezone_name: str,
        utc_offset_seconds: object,
    ) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ToolUnavailableError("Open-Meteo time is invalid") from exc
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed
        try:
            return parsed.replace(tzinfo=ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            offset = _require_integer(utc_offset_seconds, "utc_offset_seconds")
            if not -86_400 < offset < 86_400:
                raise ToolUnavailableError("Open-Meteo UTC offset is invalid")
            return parsed.replace(tzinfo=timezone(timedelta(seconds=offset)))

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise TimeoutError("Weather timeout budget exhausted")
        return remaining

    def _store_cache(
        self,
        key: str,
        output: ToolOutput,
        location: Mapping[str, Any],
        fetched_at: float,
    ) -> None:
        if key not in self._cache and len(self._cache) >= self._max_cache_entries:
            oldest_key = min(
                self._cache,
                key=lambda candidate: self._cache[candidate].fetched_at,
            )
            del self._cache[oldest_key]
        self._cache[key] = _CacheEntry(
            output=output,
            fetched_at=fetched_at,
            location=dict(location),
        )

    @staticmethod
    def _with_cache_state(output: ToolOutput, *, stale: bool) -> ToolOutput:
        data = dict(output.data)
        data["from_cache"] = True
        data["is_stale"] = stale
        return ToolOutput(
            data,
            source=output.source,
            observed_at=output.observed_at,
        )


def build_open_meteo_weather_adapter() -> OpenMeteoWeatherAdapter:
    """Build the production adapter while keeping test dependencies injectable."""
    return OpenMeteoWeatherAdapter()
