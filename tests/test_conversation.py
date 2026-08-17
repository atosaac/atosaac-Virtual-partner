from collections.abc import Sequence

import pytest

from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.conversation import ConversationService
from atosaac_virtual_partner.message import Message, MessageRole


class RecordingReplyProvider:
    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = iter(replies)
        self.contexts: list[tuple[Message, ...]] = []

    def generate_reply(self, messages: Sequence[Message]) -> str:
        self.contexts.append(tuple(messages))
        return next(self._replies)


def build_character() -> CharacterProfile:
    return CharacterProfile(
        name="atosaac",
        version="test",
        instructions="Be independent and playful.",
        source="test",
    )


def test_conversation_includes_character_and_previous_turns() -> None:
    provider = RecordingReplyProvider(("第一条回复", "第二条回复"))
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
    provider = RecordingReplyProvider(("  ",))
    conversation = ConversationService(provider, build_character())

    with pytest.raises(ValueError, match="empty reply"):
        conversation.respond("你好")

    assert tuple(conversation.history) == ()
