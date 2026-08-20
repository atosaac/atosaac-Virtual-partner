from dataclasses import dataclass
from enum import StrEnum


class MessageRole(StrEnum):
    SYSTEM = "system"
    MEMORY = "memory"
    TOOL = "tool"
    USER = "user"
    ASSISTANT = "assistant"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class Message:
    """One immutable message in a conversation."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Message content cannot be empty")
