from collections.abc import Callable

from .character import (
    DEFAULT_CHARACTER_NAME,
    CharacterProfile,
    load_default_character,
)
from .conversation import ConversationService
from .reply import MockReplyProvider, ReplyProvider, ReplyProviderError


EXIT_COMMANDS = frozenset({"exit", "quit", "退出"})
WELCOME_TEXT = "你好！输入“退出”可以结束聊天。"
GOODBYE_TEXT = "下次见。"
REPLY_ERROR_TEXT = "回复失败："
WELCOME_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {WELCOME_TEXT}"
GOODBYE_MESSAGE = f"{DEFAULT_CHARACTER_NAME}: {GOODBYE_TEXT}"
REPLY_ERROR_PREFIX = f"{DEFAULT_CHARACTER_NAME}: {REPLY_ERROR_TEXT}"


def run_chat(
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
    reply_provider: ReplyProvider | None = None,
    character_profile: CharacterProfile | None = None,
) -> None:
    """Run an interactive terminal chat session."""
    read = input if input_func is None else input_func
    write = print if output_func is None else output_func
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

        try:
            reply = conversation.respond(user_text)
        except ReplyProviderError as exc:
            write(f"{character.name}: {REPLY_ERROR_TEXT}{exc}")
            continue
        write(f"{character.name}: {reply}")
