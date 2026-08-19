from collections.abc import Iterator, Sequence

import pytest

from atosaac_virtual_partner.chat import (
    CANCELLED_MESSAGE,
    GOODBYE_MESSAGE,
    REPLY_ERROR_PREFIX,
    WELCOME_MESSAGE,
    run_chat,
)
from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.initiative import IdleInitiativePolicy
from atosaac_virtual_partner.message import Message
from atosaac_virtual_partner.reply import (
    CancellationToken,
    MetricsCallback,
    ReplyProviderError,
)


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

        def stream_reply(
            self,
            messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            self.received_contexts.append(tuple(messages))
            yield "这是测试回复"

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

        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            self.call_count += 1
            if self.call_count == 1:
                raise ReplyProviderError("temporary failure")
            yield "恢复了"

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


def test_run_chat_writes_reply_fragments_as_they_arrive() -> None:
    answers: Iterator[str] = iter(["普通消息", "退出"])
    output: list[str] = []
    fragments: list[str] = []

    class ChunkedReplyProvider:
        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            yield "这是"
            yield "流式回复"

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        stream_output_func=fragments.append,
        reply_provider=ChunkedReplyProvider(),
    )

    assert output == [WELCOME_MESSAGE, GOODBYE_MESSAGE]
    assert fragments == ["atosaac: ", "这是", "流式回复", "\n"]


def test_run_chat_cancels_only_the_current_stream_on_keyboard_interrupt() -> None:
    answers: Iterator[str] = iter(["普通消息", "退出"])
    output: list[str] = []
    fragments: list[str] = []

    class InterruptedReplyProvider:
        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            yield "未完成"
            raise KeyboardInterrupt

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        stream_output_func=fragments.append,
        reply_provider=InterruptedReplyProvider(),
    )

    assert output == [WELCOME_MESSAGE, CANCELLED_MESSAGE, GOODBYE_MESSAGE]
    assert fragments == ["atosaac: ", "未完成", "\n"]


def test_run_chat_starts_a_new_line_before_reporting_midstream_error() -> None:
    answers: Iterator[str] = iter(["普通消息", "退出"])
    output: list[str] = []
    fragments: list[str] = []

    class FailingStreamReplyProvider:
        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            yield "未完成"
            raise ReplyProviderError("stream failed")

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        stream_output_func=fragments.append,
        reply_provider=FailingStreamReplyProvider(),
    )

    assert output == [
        WELCOME_MESSAGE,
        f"{REPLY_ERROR_PREFIX}stream failed",
        GOODBYE_MESSAGE,
    ]
    assert fragments == ["atosaac: ", "未完成", "\n"]


def test_run_chat_optionally_shows_metrics_without_message_content() -> None:
    answers: Iterator[str] = iter(["私人内容", "退出"])
    output: list[str] = []

    run_chat(
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        show_metrics=True,
    )

    assert output[0] == WELCOME_MESSAGE
    assert output[1] == "atosaac: 我听到了：私人内容"
    assert output[2].startswith("[指标] 首字 ")
    assert "私人内容" not in output[2]
    assert output[3] == GOODBYE_MESSAGE


def test_run_chat_speaks_once_after_idle_and_then_waits_for_user() -> None:
    timed_answers: Iterator[str | None] = iter([None, "退出"])
    blocking_answers: Iterator[str] = iter(["这是我的答案"])
    timed_calls: list[tuple[str, float]] = []
    output: list[str] = []

    def timed_read(prompt: str, timeout_seconds: float) -> str | None:
        timed_calls.append((prompt, timeout_seconds))
        return next(timed_answers)

    run_chat(
        input_func=lambda _prompt: next(blocking_answers),
        timed_input_func=timed_read,
        output_func=output.append,
        initiative_policy=IdleInitiativePolicy(idle_seconds=30),
    )

    assert timed_calls == [("You: ", 30), ("You: ", 30)]
    assert output == [
        WELCOME_MESSAGE,
        "atosaac: 我刚想到一个问题：你现在最想把哪件小事做好？",
        "atosaac: 我听到了：这是我的答案",
        GOODBYE_MESSAGE,
    ]


def test_run_chat_requires_timed_reader_for_custom_initiative_input() -> None:
    with pytest.raises(ValueError, match="timed input"):
        run_chat(
            input_func=lambda _prompt: "退出",
            initiative_policy=IdleInitiativePolicy(idle_seconds=30),
        )
