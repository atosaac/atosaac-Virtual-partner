from collections.abc import Callable

from .character import CharacterProfile, load_default_character
from .conversation import ConversationService
from .reply import MockReplyProvider, ReplyProvider


EXIT_COMMANDS = frozenset({"exit", "quit", "退出"})
WELCOME_MESSAGE = "Virtual Partner: 你好！输入“退出”可以结束聊天。"
GOODBYE_MESSAGE = "Virtual Partner: 下次见。"


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

    write(WELCOME_MESSAGE)

    while True:
        try:
            user_text = read("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            write(GOODBYE_MESSAGE)
            return

        if not user_text:
            continue

        if user_text.casefold() in EXIT_COMMANDS:
            write(GOODBYE_MESSAGE)
            return

        reply = conversation.respond(user_text)
        write(f"Virtual Partner: {reply}")
