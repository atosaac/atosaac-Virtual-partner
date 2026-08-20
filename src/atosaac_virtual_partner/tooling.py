"""Provider-independent capability gateway for bounded application tools."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import perf_counter
from types import MappingProxyType
from typing import Protocol, TypeAlias


ToolScalar: TypeAlias = str | int | float | bool | None
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_MAX_ARGUMENTS = 16
_MAX_ARGUMENT_CHARACTERS = 500
MAX_TOOL_TIMEOUT_SECONDS = 30.0
DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0


class ToolPermission(StrEnum):
    """Classify capabilities by their potential external effect."""

    READ_ONLY = "read_only"
    EXTERNAL_ACTION = "external_action"


class ToolFailureCode(StrEnum):
    """Expose stable, content-free failure categories to callers."""

    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_ARGUMENTS = "invalid_arguments"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INTERNAL_ERROR = "internal_error"


class ToolInputError(ValueError):
    """Report invalid adapter arguments without treating them as a crash."""


class ToolUnavailableError(RuntimeError):
    """Report a temporary provider or transport failure."""


def _normalize_tool_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Tool name must be text")
    normalized = name.strip().casefold()
    if _TOOL_NAME_PATTERN.fullmatch(normalized) is None:
        raise ValueError(
            "Tool name must use lowercase letters, digits, '.', '-', or '_'"
        )
    return normalized


def _freeze_scalars(
    values: Mapping[str, ToolScalar],
    *,
    field_name: str,
) -> Mapping[str, ToolScalar]:
    if not isinstance(values, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    if len(values) > _MAX_ARGUMENTS:
        raise ValueError(f"{field_name} cannot contain more than {_MAX_ARGUMENTS} items")

    copied: dict[str, ToolScalar] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty text")
        normalized_key = key.strip()
        if normalized_key in copied:
            raise ValueError(f"{field_name} contains duplicate normalized keys")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError(f"{field_name} values must be JSON scalar values")
        if isinstance(value, str) and len(value) > _MAX_ARGUMENT_CHARACTERS:
            raise ValueError(
                f"{field_name} text values cannot exceed "
                f"{_MAX_ARGUMENT_CHARACTERS} characters"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{field_name} numeric values must be finite")
        copied[normalized_key] = value
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """Describe one validated tool request owned by the application."""

    tool_name: str
    arguments: Mapping[str, ToolScalar]
    timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds,
            (int, float),
        ):
            raise ValueError("Tool timeout must be a number")
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_TOOL_TIMEOUT_SECONDS:
            raise ValueError(
                f"Tool timeout must be greater than zero and no more than "
                f"{MAX_TOOL_TIMEOUT_SECONDS:g} seconds"
            )
        object.__setattr__(self, "tool_name", _normalize_tool_name(self.tool_name))
        object.__setattr__(
            self,
            "arguments",
            _freeze_scalars(self.arguments, field_name="Tool arguments"),
        )
        object.__setattr__(self, "timeout_seconds", timeout)


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Publish the identity and permission class of one adapter."""

    name: str
    description: str
    permission: ToolPermission

    def __post_init__(self) -> None:
        if not isinstance(self.description, str):
            raise ValueError("Tool description must be text")
        clean_description = self.description.strip()
        if not clean_description:
            raise ValueError("Tool description cannot be empty")
        if len(clean_description) > 300:
            raise ValueError("Tool description cannot exceed 300 characters")
        if not isinstance(self.permission, ToolPermission):
            raise ValueError("Tool permission is invalid")
        object.__setattr__(self, "name", _normalize_tool_name(self.name))
        object.__setattr__(self, "description", clean_description)


@dataclass(frozen=True, slots=True)
class ToolOutput:
    """Return structured data plus optional provenance from an adapter."""

    data: Mapping[str, ToolScalar]
    source: str | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.source is not None and not isinstance(self.source, str):
            raise ValueError("Tool output source must be text")
        clean_source = None if self.source is None else self.source.strip()
        if self.source is not None and not clean_source:
            raise ValueError("Tool output source cannot be empty")
        if self.observed_at is not None and (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("Tool observation time must include a timezone")
        object.__setattr__(
            self,
            "data",
            _freeze_scalars(self.data, field_name="Tool output"),
        )
        object.__setattr__(self, "source", clean_source)


class ToolAdapter(Protocol):
    """Define one small capability behind the application gateway."""

    @property
    def descriptor(self) -> ToolDescriptor: ...

    def execute(
        self,
        arguments: Mapping[str, ToolScalar],
        timeout_seconds: float,
    ) -> ToolOutput: ...


class ToolRegistry:
    """Resolve explicitly registered capabilities by stable name."""

    def __init__(self, adapters: Iterable[ToolAdapter] = ()) -> None:
        self._adapters: dict[str, ToolAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    @property
    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(
            adapter.descriptor
            for _name, adapter in sorted(self._adapters.items())
        )

    def register(self, adapter: ToolAdapter) -> None:
        descriptor = adapter.descriptor
        if descriptor.name in self._adapters:
            raise ValueError(f"Tool is already registered: {descriptor.name}")
        self._adapters[descriptor.name] = adapter

    def resolve(self, tool_name: str) -> ToolAdapter | None:
        return self._adapters.get(_normalize_tool_name(tool_name))


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Expose one safe gateway outcome without leaking exception details."""

    tool_name: str
    elapsed_seconds: float
    output: ToolOutput | None = None
    failure_code: ToolFailureCode | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("Tool elapsed time must be a non-negative finite number")
        succeeded = self.output is not None and self.failure_code is None
        failed = self.output is None and self.failure_code is not None
        if not (succeeded or failed):
            raise ValueError("Tool result must contain either output or one failure")
        if succeeded and self.message is not None:
            raise ValueError("Successful tool results cannot contain an error message")
        if failed and (self.message is None or not self.message.strip()):
            raise ValueError("Failed tool results require a safe message")
        object.__setattr__(self, "tool_name", _normalize_tool_name(self.tool_name))

    @property
    def succeeded(self) -> bool:
        return self.output is not None and self.failure_code is None


class ToolGateway:
    """Check permissions and normalize adapter success or failure outcomes."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        allowed_permissions: Iterable[ToolPermission] = (),
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        permissions = frozenset(allowed_permissions)
        if any(not isinstance(item, ToolPermission) for item in permissions):
            raise ValueError("Allowed tool permissions are invalid")
        self._registry = registry
        self._allowed_permissions = permissions
        self._clock = clock

    @property
    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return self._registry.descriptors

    def execute(self, request: ToolRequest) -> ToolResult:
        started_at = self._clock()
        adapter = self._registry.resolve(request.tool_name)
        if adapter is None:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.NOT_FOUND,
                "请求的工具当前不可用。",
            )
        if adapter.descriptor.permission not in self._allowed_permissions:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.PERMISSION_DENIED,
                "这个工具尚未获得执行权限。",
            )

        try:
            output = adapter.execute(request.arguments, request.timeout_seconds)
        except ToolInputError:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.INVALID_ARGUMENTS,
                "工具参数无效。",
            )
        except TimeoutError:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.TIMEOUT,
                "工具查询超时。",
            )
        except ToolUnavailableError:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.UNAVAILABLE,
                "工具服务暂时不可用。",
            )
        except Exception:
            return self._failure(
                request,
                started_at,
                ToolFailureCode.INTERNAL_ERROR,
                "工具执行失败。",
            )
        return ToolResult(
            tool_name=request.tool_name,
            elapsed_seconds=max(0.0, self._clock() - started_at),
            output=output,
        )

    def _failure(
        self,
        request: ToolRequest,
        started_at: float,
        code: ToolFailureCode,
        message: str,
    ) -> ToolResult:
        return ToolResult(
            tool_name=request.tool_name,
            elapsed_seconds=max(0.0, self._clock() - started_at),
            failure_code=code,
            message=message,
        )
