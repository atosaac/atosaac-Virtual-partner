from collections.abc import Iterator, Sequence

import pytest

from atosaac_virtual_partner.chat import (
    GOODBYE_MESSAGE,
    REPLY_ERROR_PREFIX,
    WELCOME_MESSAGE,
    run_chat,
)
from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.message import Message
from atosaac_virtual_partner.reply import ReplyProviderError


def test_run_chat_replies_until_user_exits() -> None:
    answers: Iterator[str] = iter(["", "你好", "EXIT"])
    prompts: list[str] = []
    output: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    run_chat(input_func=read, output_func=output.append)

    assert prompts == ["You: ", "You: ", "You: "]
    assert output == [
        WELCOME_MESSAGE,
        "atosaac: 我听到了：你好",
        GOODBYE_MESSAGE,
    ]


def test_run_chat_handles_end_of_input() -> None:
    output: list[str] = []

    def end_input(_prompt: str) -> str:
        raise EOFError

    run_chat(input_func=end_input, output_func=output.append)

    assert output == [WELCOME_MESSAGE, GOODBYE_MESSAGE]


@pytest.mark.parametrize("exit_text", ["exit", "EXIT", " quit ", "退出", " 退出 "])
def test_run_chat_accepts_supported_exit_commands(exit_text: str) -> None:
    output: list[str] = []

    run_chat(input_func=lambda _prompt: exit_text, output_func=output.append)

    assert output == [WELCOME_MESSAGE, GOODBYE_MESSAGE]


def test_run_chat_only_exits_on_an_exact_command() -> None:
    answers: Iterator[str] = iter(["exit now", "退出"])
    output: list[str] = []

    run_chat(input_func=lambda _prompt: next(answers), output_func=output.append)

    assert output == [
        WELCOME_MESSAGE,
        "atosaac: 我听到了：exit now",
        GOODBYE_MESSAGE,
    ]


def test_run_chat_handles_keyboard_interrupt() -> None:
    output: list[str] = []

    def interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    run_chat(input_func=interrupt, output_func=output.append)

    assert output == [WELCOME_MESSAGE, GOODBYE_MESSAGE]


def test_run_chat_uses_injected_reply_provider() -> None:
    answers: Iterator[str] = iter([" 你好 ", "退出"])
    output: list[str] = []

    class RecordingReplyProvider:
        def __init__(self) -> None:
            self.received_contexts: list[tuple[Message, ...]] = []

        def generate_reply(self, messages: Sequence[Message]) -> str:
            self.received_contexts.append(tuple(messages))
            return "这是测试回复"

    provider = RecordingReplyProvider()
    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        reply_provider=provider,
    )

    assert provider.received_contexts[0][-1].content == "你好"
    assert output == [
        WELCOME_MESSAGE,
        "atosaac: 这是测试回复",
        GOODBYE_MESSAGE,
    ]


def test_run_chat_uses_current_character_name_as_speaker() -> None:
    answers: Iterator[str] = iter(["你好", "退出"])
    output: list[str] = []
    character = CharacterProfile(
        name="Nova",
        version="1.0",
        instructions="Be curious.",
        source="test",
    )

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        character_profile=character,
    )

    assert output == [
        "Nova: 你好！输入“退出”可以结束聊天。",
        "Nova: 我听到了：你好",
        "Nova: 下次见。",
    ]


def test_run_chat_continues_after_reply_provider_error() -> None:
    answers: Iterator[str] = iter(["第一次", "第二次", "退出"])
    output: list[str] = []

    class RecoveringReplyProvider:
        def __init__(self) -> None:
            self.call_count = 0

        def generate_reply(self, _messages: Sequence[Message]) -> str:
            self.call_count += 1
            if self.call_count == 1:
                raise ReplyProviderError("temporary failure")
            return "恢复了"

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        reply_provider=RecoveringReplyProvider(),
    )

    assert output == [
        WELCOME_MESSAGE,
        f"{REPLY_ERROR_PREFIX}temporary failure",
        "atosaac: 恢复了",
        GOODBYE_MESSAGE,
    ]
