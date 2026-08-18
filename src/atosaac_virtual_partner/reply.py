from collections.abc import Callable, Iterator, Sequence
from threading import Event
from typing import Protocol

from .message import Message, MessageRole
from .metrics import ProviderMetrics


MetricsCallback = Callable[[ProviderMetrics], None]


class ReplyProviderError(RuntimeError):
    """Raised when a reply provider cannot generate a usable response."""


class ReplyCancelled(RuntimeError):
    """Raised when reply generation is cancelled before completion."""


class CancellationToken:
    """Share a thread-safe cancellation request with reply-generation code."""

    def __init__(self) -> None:
        self._cancelled = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise ReplyCancelled("Reply generation was cancelled")


class ReplyProvider(Protocol):
    """Define the reply behavior required by a conversation interface."""

    def stream_reply(
        self,
        messages: Sequence[Message],
        cancellation_token: CancellationToken | None = None,
        metrics_callback: MetricsCallback | None = None,
    ) -> Iterator[str]:
        """Yield reply text fragments from the supplied conversation context."""
        ...


class MockReplyProvider:
    """Generate deterministic local replies for development and tests."""

    def stream_reply(
        self,
        messages: Sequence[Message],
        cancellation_token: CancellationToken | None = None,
        metrics_callback: MetricsCallback | None = None,
    ) -> Iterator[str]:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        for message in reversed(messages):
            if message.role is MessageRole.USER:
                yield f"我听到了：{message.content}"
                if metrics_callback is not None:
                    metrics_callback(ProviderMetrics(provider_name="mock"))
                return
        raise ValueError("A user message is required to generate a reply")

    def generate_reply(self, messages: Sequence[Message]) -> str:
        """Return a complete reply for callers that do not consume streams."""
        return "".join(self.stream_reply(messages))
