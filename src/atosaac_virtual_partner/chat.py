from collections.abc import Callable
import re
import select
import sys

from .character import (
    DEFAULT_CHARACTER_NAME,
    CharacterProfile,
    load_default_character,
)
from .conversation import ConversationService
from .dialogue_policy import DEFAULT_DIALOGUE_POLICY, DialoguePolicy
from .grounding import DEFAULT_RUNTIME_GROUNDING, RuntimeGrounding
from .initiative import IdleInitiativePolicy
from .memory import MemoryStoreError
from .memory_capture import MemoryCapture
from .memory_context import MemoryContextProvider
from .metrics import format_reply_metrics
from .reply import (
    CancellationToken,
    MockReplyProvider,
    ReplyCancelled,
    ReplyProvider,
    ReplyProviderError,
)
from .tool_context import ToolContextProvider


EXIT_COMMANDS = frozenset({"exit", "quit", "退出"})
WELCOME_TEXT = "你好！输入“退出”可以结束聊天。"
GOODBYE_TEXT = "下次见。"
REPLY_ERROR_TEXT = "回复失败："
CANCELLED_TEXT = "回复已取消。"
WELCOME_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {WELCOME_TEXT}"
GOODBYE_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {GOODBYE_TEXT}"
REPLY_ERROR_PREFIX = f"{DEFAULT_CHARACTER_NAME}: {REPLY_ERROR_TEXT}"
CANCELLED_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {CANCELLED_TEXT}"

TimedInput = Callable[[str, float], str | None]
_TERMINAL_PROMPT_PREFIX = re.compile(r"^you\s*[:：]\s*", re.IGNORECASE)


def normalize_terminal_user_text(text: str) -> str:
    """Remove one accidentally pasted terminal prompt prefix."""
    normalized_text = text.strip()
    match = _TERMINAL_PROMPT_PREFIX.match(normalized_text)
    if match is None:
        return normalized_text
    return normalized_text[match.end() :].strip()


def _write_stdout_fragment(text: str) -> None:
    print(text, end="", flush=True)


def _read_terminal_with_timeout(prompt: str, timeout_seconds: float) -> str | None:
    print(prompt, end="", flush=True)
    readable, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
    if not readable:
        print()
        return None
    return input()


def run_chat(
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
    stream_output_func: Callable[[str], None] | None = None,
    reply_provider: ReplyProvider | None = None,
    character_profile: CharacterProfile | None = None,
    show_metrics: bool = False,
    initiative_policy: IdleInitiativePolicy | None = None,
    timed_input_func: TimedInput | None = None,
    dialogue_policy: DialoguePolicy = DEFAULT_DIALOGUE_POLICY,
    runtime_grounding: RuntimeGrounding = DEFAULT_RUNTIME_GROUNDING,
    memory_context_provider: MemoryContextProvider | None = None,
    memory_capture: MemoryCapture | None = None,
    tool_context_provider: ToolContextProvider | None = None,
) -> None:
    """Run an interactive terminal chat session."""
    read = input if input_func is None else input_func
    timed_read = timed_input_func
    if initiative_policy is not None and timed_read is None:
        if input_func is not None:
            raise ValueError(
                "A timed input function is required with custom input and initiative"
            )
        timed_read = _read_terminal_with_timeout
    write = print if output_func is None else output_func
    write_fragment = stream_output_func
    if write_fragment is None and output_func is None:
        write_fragment = _write_stdout_fragment
    provider = MockReplyProvider() if reply_provider is None else reply_provider
    character = (
        load_default_character() if character_profile is None else character_profile
    )
    conversation = ConversationService(
        provider,
        character,
        dialogue_policy=dialogue_policy,
        runtime_grounding=runtime_grounding,
        memory_context_provider=memory_context_provider,
        memory_capture=memory_capture,
        tool_context_provider=tool_context_provider,
    )

    write(f"{character.name}: {WELCOME_TEXT}")
    initiatives_since_user_activity = 0

    while True:
        is_initiative = False
        user_text = ""
        try:
            if initiative_policy is not None and initiative_policy.can_trigger(
                initiatives_since_user_activity
            ):
                assert timed_read is not None
                timed_value = timed_read("You: ", initiative_policy.idle_seconds)
                if timed_value is None:
                    is_initiative = True
                else:
                    user_text = normalize_terminal_user_text(timed_value)
                    initiatives_since_user_activity = 0
            else:
                user_text = normalize_terminal_user_text(read("You: "))
                initiatives_since_user_activity = 0
        except (EOFError, KeyboardInterrupt):
            write(f"{character.name}: {GOODBYE_TEXT}")
            return

        if not is_initiative:
            if not user_text:
                continue

            if user_text.casefold() in EXIT_COMMANDS:
                write(f"{character.name}: {GOODBYE_TEXT}")
                return

        cancellation_token = CancellationToken()
        reply_chunks: list[str] = []
        started_stream = False
        try:
            if is_initiative:
                assert initiative_policy is not None
                reply_stream = conversation.stream_initiative(
                    initiative_policy.event_instructions(),
                    cancellation_token=cancellation_token,
                )
            else:
                reply_stream = conversation.stream_response(
                    user_text,
                    cancellation_token=cancellation_token,
                )
            for chunk in reply_stream:
                reply_chunks.append(chunk)
                if write_fragment is None:
                    continue
                if not started_stream:
                    write_fragment(f"{character.name}: ")
                    started_stream = True
                write_fragment(chunk)
        except (KeyboardInterrupt, ReplyCancelled):
            cancellation_token.cancel()
            if is_initiative:
                initiatives_since_user_activity += 1
            if started_stream and write_fragment is not None:
                write_fragment("\n")
            write(f"{character.name}: {CANCELLED_TEXT}")
            continue
        except (MemoryStoreError, ReplyProviderError) as exc:
            if is_initiative:
                initiatives_since_user_activity += 1
            if started_stream and write_fragment is not None:
                write_fragment("\n")
            write(f"{character.name}: {REPLY_ERROR_TEXT}{exc}")
            continue

        if write_fragment is None:
            write(f"{character.name}: {''.join(reply_chunks).strip()}")
        else:
            write_fragment("\n")

        if is_initiative:
            initiatives_since_user_activity += 1

        if show_metrics and conversation.last_metrics is not None:
            write(format_reply_metrics(conversation.last_metrics))
