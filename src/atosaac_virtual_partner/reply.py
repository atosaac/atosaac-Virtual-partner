from collections.abc import Sequence
from typing import Protocol

from .message import Message, MessageRole


class ReplyProvider(Protocol):
    """Define the reply behavior required by a conversation interface."""

    def generate_reply(self, messages: Sequence[Message]) -> str:
        """Generate one reply from system instructions and conversation context."""
        ...


class MockReplyProvider:
    """Generate deterministic local replies for development and tests."""

    def generate_reply(self, messages: Sequence[Message]) -> str:
        for message in reversed(messages):
            if message.role is MessageRole.USER:
                return f"我听到了：{message.content}"
        raise ValueError("A user message is required to generate a reply")
