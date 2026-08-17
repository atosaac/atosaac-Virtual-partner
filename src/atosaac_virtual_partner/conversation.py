from collections.abc import Sequence

from .character import CharacterProfile
from .message import Message, MessageRole
from .reply import ReplyProvider


class ConversationService:
    """Coordinate character context, message history, and reply generation."""

    def __init__(
        self,
        reply_provider: ReplyProvider,
        character: CharacterProfile,
    ) -> None:
        self._reply_provider = reply_provider
        self._character = character
        self._history: list[Message] = []

    @property
    def character(self) -> CharacterProfile:
        return self._character

    @property
    def history(self) -> Sequence[Message]:
        return tuple(self._history)

    def respond(self, user_text: str) -> str:
        """Generate a reply and record a successful conversation turn."""
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("User text cannot be empty")

        user_message = Message(MessageRole.USER, normalized_text)
        context = (
            Message(MessageRole.SYSTEM, self._character.instructions),
            *self._history,
            user_message,
        )
        reply_text = self._reply_provider.generate_reply(context).strip()
        if not reply_text:
            raise ValueError("Reply provider returned an empty reply")

        self._history.extend(
            (
                user_message,
                Message(MessageRole.ASSISTANT, reply_text),
            )
        )
        return reply_text
