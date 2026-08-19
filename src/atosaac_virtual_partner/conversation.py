from collections.abc import Callable, Iterator, Sequence
from time import perf_counter

from .character import CharacterProfile
from .context import DEFAULT_CONTEXT_WINDOW_POLICY, ContextWindowPolicy
from .dialogue_policy import (
    DEFAULT_DIALOGUE_POLICY,
    DialogueGuidance,
    DialoguePolicy,
)
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
        context_window_policy: ContextWindowPolicy = DEFAULT_CONTEXT_WINDOW_POLICY,
        dialogue_policy: DialoguePolicy = DEFAULT_DIALOGUE_POLICY,
    ) -> None:
        self._reply_provider = reply_provider
        self._character = character
        self._runtime_grounding = runtime_grounding
        self._context_window_policy = context_window_policy
        self._dialogue_policy = dialogue_policy
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

        user_message = Message(MessageRole.USER, normalized_text)
        dialogue_guidance = self._dialogue_policy.guide(
            normalized_text,
            self._history,
        )
        yield from self._stream_turn(
            user_message,
            cancellation_token,
            dialogue_guidance=dialogue_guidance,
        )

    def stream_initiative(
        self,
        event_instructions: str,
        cancellation_token: CancellationToken | None = None,
    ) -> Iterator[str]:
        """Yield an application-triggered reply and preserve its event context."""
        normalized_instructions = event_instructions.strip()
        if not normalized_instructions:
            raise ValueError("Initiative event instructions cannot be empty")
        event_message = Message(MessageRole.EVENT, normalized_instructions)
        yield from self._stream_turn(event_message, cancellation_token)

    def _stream_turn(
        self,
        trigger_message: Message,
        cancellation_token: CancellationToken | None,
        dialogue_guidance: DialogueGuidance | None = None,
    ) -> Iterator[str]:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        self._last_metrics = None
        started_at = self._clock()
        first_text_seconds: float | None = None
        provider_metrics: ProviderMetrics | None = None
        local_fallback_used = False

        def receive_metrics(metrics: ProviderMetrics) -> None:
            nonlocal provider_metrics
            provider_metrics = metrics

        selected_history = self._context_window_policy.select_history(self._history)
        system_context = [
            Message(MessageRole.SYSTEM, self._character.instructions),
            Message(
                MessageRole.SYSTEM,
                self._runtime_grounding.system_instructions(),
            ),
        ]
        if dialogue_guidance is not None:
            system_context.append(
                Message(
                    MessageRole.SYSTEM,
                    dialogue_guidance.system_instructions,
                )
            )
        context = (
            *system_context,
            *selected_history,
            trigger_message,
        )
        reply_chunks: list[str] = []
        reply_constraint = (
            None
            if dialogue_guidance is None
            else dialogue_guidance.reply_constraint
        )
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
            if first_text_seconds is None and reply_constraint is None:
                first_text_seconds = self._clock() - started_at
            reply_chunks.append(chunk)
            if reply_constraint is None:
                yield chunk

        token.raise_if_cancelled()
        generated_text = "".join(reply_chunks).strip()
        if not generated_text:
            raise ValueError("Reply provider returned an empty reply")
        reply_text = generated_text
        if reply_constraint is not None:
            if not reply_constraint.accepts(generated_text):
                reply_text = reply_constraint.fallback_text
                local_fallback_used = True
            first_text_seconds = self._clock() - started_at
            yield reply_text
            token.raise_if_cancelled()
        if first_text_seconds is None:
            raise ValueError("Reply provider returned no measurable text")

        total_seconds = self._clock() - started_at

        self._history.extend(
            (
                trigger_message,
                Message(MessageRole.ASSISTANT, reply_text),
            )
        )
        self._last_metrics = ReplyMetrics(
            first_text_seconds=first_text_seconds,
            total_seconds=total_seconds,
            provider=provider_metrics,
            local_fallback_used=local_fallback_used,
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

    def initiate(
        self,
        event_instructions: str,
        cancellation_token: CancellationToken | None = None,
    ) -> str:
        """Return one complete application-triggered reply."""
        return "".join(
            self.stream_initiative(
                event_instructions,
                cancellation_token=cancellation_token,
            )
        ).strip()
