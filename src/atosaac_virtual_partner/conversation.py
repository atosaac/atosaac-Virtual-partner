from collections.abc import Iterator, Sequence

from .character import CharacterProfile
from .message import Message, MessageRole
from .reply import CancellationToken, ReplyProvider


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

    def stream_response(
        self,
        user_text: str,
        cancellation_token: CancellationToken | None = None,
    ) -> Iterator[str]:
        """Yield one reply and record the turn only after complete generation."""
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("User text cannot be empty")

        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        user_message = Message(MessageRole.USER, normalized_text)
        context = (
            Message(MessageRole.SYSTEM, self._character.instructions),
            *self._history,
            user_message,
        )
        reply_chunks: list[str] = []
        for chunk in self._reply_provider.stream_reply(context, token):
            token.raise_if_cancelled()
            if not isinstance(chunk, str):
                raise ValueError("Reply provider yielded a non-text chunk")
            if not chunk:
                continue
            reply_chunks.append(chunk)
            yield chunk

        token.raise_if_cancelled()
        reply_text = "".join(reply_chunks).strip()
        if not reply_text:
            raise ValueError("Reply provider returned an empty reply")

        self._history.extend(
            (
                user_message,
                Message(MessageRole.ASSISTANT, reply_text),
            )
        )

    def respond(
        self,
        user_text: str,
        cancellation_token: CancellationToken | None = None,
    ) -> str:
        """Return a complete reply while preserving streaming transaction rules."""
        return "".join(
            self.stream_response(
                user_text,
                cancellation_token=cancellation_token,
            )
        ).strip()
