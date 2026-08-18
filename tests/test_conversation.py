from collections.abc import Iterator, Sequence

import pytest

from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.conversation import ConversationService
from atosaac_virtual_partner.message import Message, MessageRole
from atosaac_virtual_partner.reply import (
    CancellationToken,
    ReplyCancelled,
    ReplyProviderError,
)


class RecordingReplyProvider:
    def __init__(self, replies: Sequence[Sequence[str]]) -> None:
        self._replies = iter(replies)
        self.contexts: list[tuple[Message, ...]] = []

    def stream_reply(
        self,
        messages: Sequence[Message],
        cancellation_token: CancellationToken | None = None,
    ) -> Iterator[str]:
        self.contexts.append(tuple(messages))
        yield from next(self._replies)


def build_character() -> CharacterProfile:
    return CharacterProfile(
        name="atosaac",
        version="test",
        instructions="Be independent and playful.",
        source="test",
    )


def test_conversation_includes_character_and_previous_turns() -> None:
    provider = RecordingReplyProvider((("第一条", "回复"), ("第二条回复",)))
    conversation = ConversationService(provider, build_character())

    first_reply = conversation.respond(" 你好 ")
    second_reply = conversation.respond("还记得吗？")

    assert first_reply == "第一条回复"
    assert second_reply == "第二条回复"
    assert provider.contexts[0] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(MessageRole.USER, "你好"),
    )
    assert provider.contexts[1] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(MessageRole.USER, "你好"),
        Message(MessageRole.ASSISTANT, "第一条回复"),
        Message(MessageRole.USER, "还记得吗？"),
    )
    assert tuple(conversation.history) == provider.contexts[1][1:] + (
        Message(MessageRole.ASSISTANT, "第二条回复"),
    )


def test_conversation_does_not_record_failed_reply() -> None:
    provider = RecordingReplyProvider((("  ",),))
    conversation = ConversationService(provider, build_character())

    with pytest.raises(ValueError, match="empty reply"):
        conversation.respond("你好")

    assert tuple(conversation.history) == ()


def test_streaming_conversation_commits_history_only_after_completion() -> None:
    provider = RecordingReplyProvider((("第一段", "第二段"),))
    conversation = ConversationService(provider, build_character())

    reply_stream = conversation.stream_response("你好")

    assert next(reply_stream) == "第一段"
    assert tuple(conversation.history) == ()
    assert list(reply_stream) == ["第二段"]
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "你好"),
        Message(MessageRole.ASSISTANT, "第一段第二段"),
    )


def test_cancelled_stream_does_not_record_partial_reply() -> None:
    provider = RecordingReplyProvider((("第一段", "第二段"),))
    conversation = ConversationService(provider, build_character())
    cancellation_token = CancellationToken()
    reply_stream = conversation.stream_response(
        "你好",
        cancellation_token=cancellation_token,
    )

    assert next(reply_stream) == "第一段"
    cancellation_token.cancel()

    with pytest.raises(ReplyCancelled):
        next(reply_stream)

    assert tuple(conversation.history) == ()


def test_failed_stream_does_not_record_partial_reply() -> None:
    class FailingReplyProvider:
        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
        ) -> Iterator[str]:
            yield "第一段"
            raise ReplyProviderError("stream failed")

    conversation = ConversationService(FailingReplyProvider(), build_character())

    with pytest.raises(ReplyProviderError, match="stream failed"):
        list(conversation.stream_response("你好"))

    assert tuple(conversation.history) == ()
