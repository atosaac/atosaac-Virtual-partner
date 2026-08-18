from collections.abc import Callable, Iterator, Sequence
from time import perf_counter

from .character import CharacterProfile
from .grounding import DEFAULT_RUNTIME_GROUNDING, RuntimeGrounding
from .message import Message, MessageRole
from .metrics import ProviderMetrics, ReplyMetrics
from .reply import CancellationToken, ReplyProvider


class ConversationService:
    """Coordinate character context, message history, and reply generation."""

    def __init__(
        self,
        reply_provider: ReplyProvider,
        character: CharacterProfile,
        clock: Callable[[], float] = perf_counter,
        runtime_grounding: RuntimeGrounding = DEFAULT_RUNTIME_GROUNDING,
    ) -> None:
        self._reply_provider = reply_provider
        self._character = character
        self._runtime_grounding = runtime_grounding
        self._clock = clock
        self._history: list[Message] = []
        self._last_metrics: ReplyMetrics | None = None

    @property
    def character(self) -> CharacterProfile:
        return self._character

    @property
    def history(self) -> Sequence[Message]:
        return tuple(self._history)

    @property
    def last_metrics(self) -> ReplyMetrics | None:
        return self._last_metrics

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
        self._last_metrics = None
        started_at = self._clock()
        first_text_seconds: float | None = None
        provider_metrics: ProviderMetrics | None = None

        def receive_metrics(metrics: ProviderMetrics) -> None:
            nonlocal provider_metrics
            provider_metrics = metrics

        user_message = Message(MessageRole.USER, normalized_text)
        context = (
            Message(MessageRole.SYSTEM, self._character.instructions),
            Message(
                MessageRole.SYSTEM,
                self._runtime_grounding.system_instructions(),
            ),
            *self._history,
            user_message,
        )
        reply_chunks: list[str] = []
        for chunk in self._reply_provider.stream_reply(
            context,
            token,
            metrics_callback=receive_metrics,
        ):
            token.raise_if_cancelled()
            if not isinstance(chunk, str):
                raise ValueError("Reply provider yielded a non-text chunk")
            if not chunk:
                continue
            if first_text_seconds is None:
                first_text_seconds = self._clock() - started_at
            reply_chunks.append(chunk)
            yield chunk

        token.raise_if_cancelled()
        reply_text = "".join(reply_chunks).strip()
        if not reply_text:
            raise ValueError("Reply provider returned an empty reply")
        if first_text_seconds is None:
            raise ValueError("Reply provider returned no measurable text")

        total_seconds = self._clock() - started_at

        self._history.extend(
            (
                user_message,
                Message(MessageRole.ASSISTANT, reply_text),
            )
        )
        self._last_metrics = ReplyMetrics(
            first_text_seconds=first_text_seconds,
            total_seconds=total_seconds,
            provider=provider_metrics,
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
