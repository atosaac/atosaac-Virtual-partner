import pytest

from atosaac_virtual_partner.message import Message, MessageRole
from atosaac_virtual_partner.reply import MockReplyProvider


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

    with pytest.raises(ValueError, match="user message"):
        provider.generate_reply((Message(MessageRole.SYSTEM, "Test character"),))
