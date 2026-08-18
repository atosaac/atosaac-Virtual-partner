from collections.abc import Callable

from .character import (
    DEFAULT_CHARACTER_NAME,
    CharacterProfile,
    load_default_character,
)
from .conversation import ConversationService
from .metrics import format_reply_metrics
from .reply import (
    CancellationToken,
    MockReplyProvider,
    ReplyCancelled,
    ReplyProvider,
    ReplyProviderError,
)


EXIT_COMMANDS = frozenset({"exit", "quit", "退出"})
WELCOME_TEXT = "你好！输入“退出”可以结束聊天。"
GOODBYE_TEXT = "下次见。"
REPLY_ERROR_TEXT = "回复失败："
CANCELLED_TEXT = "回复已取消。"
WELCOME_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {WELCOME_TEXT}"
GOODBYE_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {GOODBYE_TEXT}"
REPLY_ERROR_PREFIX = f"{DEFAULT_CHARACTER_NAME}: {REPLY_ERROR_TEXT}"
CANCELLED_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {CANCELLED_TEXT}"


def _write_stdout_fragment(text: str) -> None:
    print(text, end="", flush=True)


def run_chat(
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
    stream_output_func: Callable[[str], None] | None = None,
    reply_provider: ReplyProvider | None = None,
    character_profile: CharacterProfile | None = None,
    show_metrics: bool = False,
) -> None:
    """Run an interactive terminal chat session."""
    read = input if input_func is None else input_func
    write = print if output_func is None else output_func
    write_fragment = stream_output_func
    if write_fragment is None and output_func is None:
        write_fragment = _write_stdout_fragment
    provider = MockReplyProvider() if reply_provider is None else reply_provider
    character = (
        load_default_character() if character_profile is None else character_profile
    )
    conversation = ConversationService(provider, character)

    write(f"{character.name}: {WELCOME_TEXT}")

    while True:
        try:
            user_text = read("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            write(f"{character.name}: {GOODBYE_TEXT}")
            return

        if not user_text:
            continue

        if user_text.casefold() in EXIT_COMMANDS:
            write(f"{character.name}: {GOODBYE_TEXT}")
            return

        cancellation_token = CancellationToken()
        reply_chunks: list[str] = []
        started_stream = False
        try:
            for chunk in conversation.stream_response(
                user_text,
                cancellation_token=cancellation_token,
            ):
                reply_chunks.append(chunk)
                if write_fragment is None:
                    continue
                if not started_stream:
                    write_fragment(f"{character.name}: ")
                    started_stream = True
                write_fragment(chunk)
        except (KeyboardInterrupt, ReplyCancelled):
            cancellation_token.cancel()
            if started_stream and write_fragment is not None:
                write_fragment("\n")
            write(f"{character.name}: {CANCELLED_TEXT}")
            continue
        except ReplyProviderError as exc:
            if started_stream and write_fragment is not None:
                write_fragment("\n")
            write(f"{character.name}: {REPLY_ERROR_TEXT}{exc}")
            continue

        if write_fragment is None:
            write(f"{character.name}: {''.join(reply_chunks).strip()}")
        else:
            write_fragment("\n")

        if show_metrics and conversation.last_metrics is not None:
            write(format_reply_metrics(conversation.last_metrics))
