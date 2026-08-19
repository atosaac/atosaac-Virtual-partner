import pytest

from atosaac_virtual_partner.message import Message, MessageRole
from atosaac_virtual_partner.reply import (
    CancellationToken,
    MockReplyProvider,
    ReplyCancelled,
)


def test_mock_reply_provider_repeats_user_input() -> None:
    provider = MockReplyProvider()

    reply = provider.generate_reply(
        (
            Message(MessageRole.SYSTEM, "Test character"),
            Message(MessageRole.USER, "你好"),
        )
    )

    assert reply == "我听到了：你好"


def test_mock_reply_provider_requires_user_message() -> None:
    provider = MockReplyProvider()

    with pytest.raises(ValueError, match="user message or application event"):
        provider.generate_reply((Message(MessageRole.SYSTEM, "Test character"),))


def test_mock_reply_provider_handles_application_event() -> None:
    provider = MockReplyProvider()

    reply = provider.generate_reply(
        (
            Message(MessageRole.SYSTEM, "Test character"),
            Message(MessageRole.EVENT, "The user is idle."),
        )
    )

    assert reply == "我刚想到一个问题：你现在最想把哪件小事做好？"


def test_mock_reply_provider_honors_cancellation_before_generation() -> None:
    provider = MockReplyProvider()
    cancellation_token = CancellationToken()
    cancellation_token.cancel()

    with pytest.raises(ReplyCancelled):
        list(
            provider.stream_reply(
                (Message(MessageRole.USER, "你好"),),
                cancellation_token=cancellation_token,
            )
        )
