from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .message import Message, MessageRole


DEFAULT_RECENT_TURNS = 8


class ContextWindowPolicy(Protocol):
    """Select the conversation history sent to a reply provider."""

    def select_history(self, history: Sequence[Message]) -> tuple[Message, ...]: ...


@dataclass(frozen=True, slots=True)
class FullHistoryContextPolicy:
    """Keep every committed message as a safe compatibility fallback."""

    def select_history(self, history: Sequence[Message]) -> tuple[Message, ...]:
        return tuple(history)


@dataclass(frozen=True, slots=True)
class RecentTurnsContextPolicy:
    """Keep the newest complete user turns without modifying stored history."""

    max_turns: int = DEFAULT_RECENT_TURNS

    def __post_init__(self) -> None:
        if isinstance(self.max_turns, bool) or not isinstance(self.max_turns, int):
            raise ValueError("Context max_turns must be an integer")
        if self.max_turns <= 0:
            raise ValueError("Context max_turns must be greater than zero")

    def select_history(self, history: Sequence[Message]) -> tuple[Message, ...]:
        messages = tuple(history)
        if not messages:
            return ()
        turn_roles = {MessageRole.USER, MessageRole.EVENT}
        if messages[0].role not in turn_roles:
            raise ValueError(
                "Conversation history must start with a user message or event"
            )
        context_only_roles = {MessageRole.SYSTEM, MessageRole.MEMORY}
        if any(message.role in context_only_roles for message in messages):
            raise ValueError(
                "Conversation history cannot contain system messages or memory messages"
            )

        turn_starts = tuple(
            index
            for index, message in enumerate(messages)
            if message.role in turn_roles
        )
        selected_turn = max(0, len(turn_starts) - self.max_turns)
        selected_start = turn_starts[selected_turn]
        return messages[selected_start:]


DEFAULT_CONTEXT_WINDOW_POLICY = RecentTurnsContextPolicy()
