from collections.abc import Iterator, Sequence

import pytest

from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.context import RecentTurnsContextPolicy
from atosaac_virtual_partner.conversation import ConversationService
from atosaac_virtual_partner.dialogue_policy import (
    DEFAULT_DIALOGUE_POLICY,
    PassthroughDialoguePolicy,
)
from atosaac_virtual_partner.grounding import (
    DEFAULT_RUNTIME_GROUNDING,
    RuntimeGrounding,
)
from atosaac_virtual_partner.message import Message, MessageRole
from atosaac_virtual_partner.memory import MemoryStoreError
from atosaac_virtual_partner.memory_capture import MemoryCaptureResult
from atosaac_virtual_partner.metrics import ProviderMetrics, ReplyMetrics, ToolMetrics
from atosaac_virtual_partner.reply import (
    CancellationToken,
    MetricsCallback,
    ReplyCancelled,
    ReplyProviderError,
)
from atosaac_virtual_partner.tool_context import ToolContext


class RecordingReplyProvider:
    def __init__(self, replies: Sequence[Sequence[str]]) -> None:
        self._replies = iter(replies)
        self.contexts: list[tuple[Message, ...]] = []

    def stream_reply(
        self,
        messages: Sequence[Message],
        cancellation_token: CancellationToken | None = None,
        metrics_callback: MetricsCallback | None = None,
    ) -> Iterator[str]:
        self.contexts.append(tuple(messages))
        yield from next(self._replies)
        if metrics_callback is not None:
            metrics_callback(
                ProviderMetrics(
                    provider_name="test",
                    input_tokens=10,
                    output_tokens=2,
                    generation_seconds=0.5,
                )
            )


class UnexpectedMemoryCapture:
    def capture(self, _user_text: str) -> MemoryCaptureResult:
        raise AssertionError("incomplete turns must not become durable memory")


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
        Message(
            MessageRole.SYSTEM,
            DEFAULT_RUNTIME_GROUNDING.system_instructions(),
        ),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_DIALOGUE_POLICY.guide("你好", ()).system_instructions,
        ),
        Message(MessageRole.USER, "你好"),
    )
    assert provider.contexts[1] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_RUNTIME_GROUNDING.system_instructions(),
        ),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_DIALOGUE_POLICY.guide(
                "还记得吗？",
                (
                    Message(MessageRole.USER, "你好"),
                    Message(MessageRole.ASSISTANT, "第一条回复"),
                ),
            ).system_instructions,
        ),
        Message(MessageRole.USER, "你好"),
        Message(MessageRole.ASSISTANT, "第一条回复"),
        Message(MessageRole.USER, "还记得吗？"),
    )
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "你好"),
        Message(MessageRole.ASSISTANT, "第一条回复"),
        Message(MessageRole.USER, "还记得吗？"),
        Message(MessageRole.ASSISTANT, "第二条回复"),
    )


def test_conversation_does_not_record_failed_reply() -> None:
    provider = RecordingReplyProvider((("  ",),))
    conversation = ConversationService(provider, build_character())

    with pytest.raises(ValueError, match="empty reply"):
        conversation.respond("你好")

    assert tuple(conversation.history) == ()
    assert conversation.last_metrics is None


def test_streaming_conversation_commits_history_only_after_completion() -> None:
    provider = RecordingReplyProvider((("第一段", "第二段"),))
    conversation = ConversationService(provider, build_character())

    reply_stream = conversation.stream_response("普通消息")

    assert next(reply_stream) == "第一段"
    assert tuple(conversation.history) == ()
    assert conversation.last_metrics is None
    assert list(reply_stream) == ["第二段"]
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "普通消息"),
        Message(MessageRole.ASSISTANT, "第一段第二段"),
    )


def test_cancelled_stream_does_not_record_partial_reply() -> None:
    provider = RecordingReplyProvider((("第一段", "第二段"),))
    conversation = ConversationService(
        provider,
        build_character(),
        memory_capture=UnexpectedMemoryCapture(),
    )
    cancellation_token = CancellationToken()
    reply_stream = conversation.stream_response(
        "普通消息",
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
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            yield "第一段"
            raise ReplyProviderError("stream failed")

    conversation = ConversationService(
        FailingReplyProvider(),
        build_character(),
        memory_capture=UnexpectedMemoryCapture(),
    )

    with pytest.raises(ReplyProviderError, match="stream failed"):
        list(conversation.stream_response("你好"))

    assert tuple(conversation.history) == ()
    assert conversation.last_metrics is None


def test_conversation_records_safe_metrics_for_completed_reply() -> None:
    provider = RecordingReplyProvider((("第一段", "第二段"),))
    clock_values = iter((10.0, 10.25, 11.5))
    conversation = ConversationService(
        provider,
        build_character(),
        clock=lambda: next(clock_values),
    )

    assert conversation.respond("你好") == "第一段第二段"
    assert conversation.last_metrics == ReplyMetrics(
        first_text_seconds=0.25,
        total_seconds=1.5,
        provider=ProviderMetrics(
            provider_name="test",
            input_tokens=10,
            output_tokens=2,
            generation_seconds=0.5,
        ),
    )


def test_conversation_sends_recent_turns_but_preserves_complete_history() -> None:
    provider = RecordingReplyProvider(
        (("reply 1",), ("reply 2",), ("reply 3",), ("reply 4",))
    )
    conversation = ConversationService(
        provider,
        build_character(),
        context_window_policy=RecentTurnsContextPolicy(max_turns=2),
    )

    for turn in range(1, 5):
        conversation.respond(f"message {turn}")

    assert provider.contexts[3][-5:] == (
        Message(MessageRole.USER, "message 2"),
        Message(MessageRole.ASSISTANT, "reply 2"),
        Message(MessageRole.USER, "message 3"),
        Message(MessageRole.ASSISTANT, "reply 3"),
        Message(MessageRole.USER, "message 4"),
    )
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "message 1"),
        Message(MessageRole.ASSISTANT, "reply 1"),
        Message(MessageRole.USER, "message 2"),
        Message(MessageRole.ASSISTANT, "reply 2"),
        Message(MessageRole.USER, "message 3"),
        Message(MessageRole.ASSISTANT, "reply 3"),
        Message(MessageRole.USER, "message 4"),
        Message(MessageRole.ASSISTANT, "reply 4"),
    )


def test_conversation_records_initiative_event_for_follow_up_context() -> None:
    provider = RecordingReplyProvider((("主动问题",), ("继续回复",)))
    conversation = ConversationService(provider, build_character())

    assert conversation.initiate("The user has been quiet.") == "主动问题"
    assert conversation.respond("我的答案") == "继续回复"

    event = Message(MessageRole.EVENT, "The user has been quiet.")
    assert provider.contexts[0][-1] == event
    assert provider.contexts[1][-3:] == (
        event,
        Message(MessageRole.ASSISTANT, "主动问题"),
        Message(MessageRole.USER, "我的答案"),
    )
    assert tuple(conversation.history) == (
        event,
        Message(MessageRole.ASSISTANT, "主动问题"),
        Message(MessageRole.USER, "我的答案"),
        Message(MessageRole.ASSISTANT, "继续回复"),
    )


def test_failed_initiative_does_not_record_event_or_partial_reply() -> None:
    class FailingInitiativeProvider:
        def stream_reply(
            self,
            _messages: Sequence[Message],
            cancellation_token: CancellationToken | None = None,
            metrics_callback: MetricsCallback | None = None,
        ) -> Iterator[str]:
            yield "没说完"
            raise ReplyProviderError("initiative failed")

    conversation = ConversationService(
        FailingInitiativeProvider(),
        build_character(),
    )

    with pytest.raises(ReplyProviderError, match="initiative failed"):
        list(conversation.stream_initiative("idle event"))

    assert tuple(conversation.history) == ()


def test_conversation_can_disable_per_turn_dialogue_guidance() -> None:
    provider = RecordingReplyProvider((("普通回复",),))
    conversation = ConversationService(
        provider,
        build_character(),
        dialogue_policy=PassthroughDialoguePolicy(),
    )

    assert conversation.respond("普通陈述") == "普通回复"
    assert provider.contexts[0] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_RUNTIME_GROUNDING.system_instructions(),
        ),
        Message(MessageRole.USER, "普通陈述"),
    )


def test_strict_turn_buffers_and_replaces_an_invalid_generated_reply() -> None:
    provider = RecordingReplyProvider((("晚上好。", "你今天怎么样？"),))
    conversation = ConversationService(provider, build_character())

    reply_stream = conversation.stream_response("晚上好～")

    assert next(reply_stream) == "晚上好～你这个波浪号把气氛带亮了。"
    assert tuple(conversation.history) == ()
    assert list(reply_stream) == []
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.local_fallback_used is True
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "晚上好～"),
        Message(
            MessageRole.ASSISTANT,
            "晚上好～你这个波浪号把气氛带亮了。",
        ),
    )


def test_strict_turn_keeps_a_valid_buffered_reply() -> None:
    provider = RecordingReplyProvider((("晚上好～", "这个开场挺轻快。"),))
    conversation = ConversationService(provider, build_character())

    assert list(conversation.stream_response("晚上好～")) == [
        "晚上好～这个开场挺轻快。"
    ]
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.local_fallback_used is False


def test_conversation_records_content_free_grounding_risks() -> None:
    provider = RecordingReplyProvider(
        (("你上次煮的那锅粥，我到现在还记得。",),)
    )
    conversation = ConversationService(provider, build_character())

    conversation.respond("我会做饭。")

    assert conversation.last_metrics is not None
    assert conversation.last_metrics.grounding_risks == (
        "unsupported_memory",
    )


def test_conversation_injects_memory_as_system_data_without_persisting_it() -> None:
    class StaticMemoryContext:
        def system_instructions(self, query: str) -> str:
            assert query == "今天上班。"
            return "# 长期记忆\n[\"你在金店工作。\"]"

    provider = RecordingReplyProvider((("店里应该挺忙。",),))
    grounding = RuntimeGrounding(persistent_memory_available=True)
    conversation = ConversationService(
        provider,
        build_character(),
        runtime_grounding=grounding,
        memory_context_provider=StaticMemoryContext(),
    )

    conversation.respond("今天上班。")

    assert provider.contexts[0][:4] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(MessageRole.SYSTEM, grounding.system_instructions()),
        Message(MessageRole.MEMORY, '# 长期记忆\n["你在金店工作。"]'),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_DIALOGUE_POLICY.guide("今天上班。", ()).system_instructions,
        ),
    )
    assert tuple(conversation.history) == (
        Message(MessageRole.USER, "今天上班。"),
        Message(MessageRole.ASSISTANT, "店里应该挺忙。"),
    )


def test_conversation_injects_ephemeral_tool_result_and_records_metrics() -> None:
    tool_metrics = ToolMetrics(
        tool_name="weather.current",
        elapsed_seconds=0.25,
        succeeded=True,
    )

    class StaticToolContext:
        def context_for(self, user_text: str) -> ToolContext:
            assert user_text == "今天会下雨吗？"
            return ToolContext(
                '# 当前回合工具结果\n{"condition":"阵雨"}',
                tool_metrics,
            )

    grounding = RuntimeGrounding(enabled_tools=("weather.current",))
    provider = RecordingReplyProvider((("可能有阵雨，带把伞吧。",),))
    conversation = ConversationService(
        provider,
        build_character(),
        runtime_grounding=grounding,
        tool_context_provider=StaticToolContext(),
    )

    conversation.respond("今天会下雨吗？")

    assert provider.contexts[0][:4] == (
        Message(MessageRole.SYSTEM, "Be independent and playful."),
        Message(MessageRole.SYSTEM, grounding.system_instructions()),
        Message(
            MessageRole.TOOL,
            '# 当前回合工具结果\n{"condition":"阵雨"}',
        ),
        Message(
            MessageRole.SYSTEM,
            DEFAULT_DIALOGUE_POLICY.guide(
                "今天会下雨吗？",
                (),
            ).system_instructions,
        ),
    )
    assert all(
        message.role is not MessageRole.TOOL for message in conversation.history
    )
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.tool == tool_metrics


def test_conversation_does_not_run_user_tool_planner_for_initiative() -> None:
    class UnexpectedToolContext:
        def context_for(self, _user_text: str) -> ToolContext:
            raise AssertionError("initiative must not trigger a user weather query")

    provider = RecordingReplyProvider((("主动问候",),))
    conversation = ConversationService(
        provider,
        build_character(),
        tool_context_provider=UnexpectedToolContext(),
    )

    assert conversation.initiate("idle event") == "主动问候"


def test_conversation_captures_memory_only_after_completed_user_turn() -> None:
    class RecordingCapture:
        def __init__(self) -> None:
            self.user_texts: list[str] = []

        def capture(self, user_text: str) -> MemoryCaptureResult:
            self.user_texts.append(user_text)
            return MemoryCaptureResult(created=1)

    provider = RecordingReplyProvider((("收到", "了。"),))
    capture = RecordingCapture()
    conversation = ConversationService(
        provider,
        build_character(),
        memory_capture=capture,
    )

    reply_stream = conversation.stream_response("我喜欢蓝色。")
    assert next(reply_stream) == "收到"
    assert capture.user_texts == []

    assert list(reply_stream) == ["了。"]
    assert capture.user_texts == ["我喜欢蓝色。"]
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.memory_created == 1


def test_conversation_skips_memory_capture_for_application_event() -> None:
    class UnexpectedCapture:
        def capture(self, _user_text: str) -> MemoryCaptureResult:
            raise AssertionError("initiative must not become user memory")

    provider = RecordingReplyProvider((("主动问候",),))
    conversation = ConversationService(
        provider,
        build_character(),
        memory_capture=UnexpectedCapture(),
    )

    assert conversation.initiate("idle event") == "主动问候"


def test_conversation_falls_back_when_memory_read_fails() -> None:
    class FailingMemoryContext:
        def system_instructions(self, _query: str) -> str:
            raise MemoryStoreError("database unavailable")

    provider = RecordingReplyProvider((("仍然回复",),))
    conversation = ConversationService(
        provider,
        build_character(),
        runtime_grounding=RuntimeGrounding(persistent_memory_available=True),
        memory_context_provider=FailingMemoryContext(),
    )

    assert conversation.respond("普通消息") == "仍然回复"
    assert all(
        message.role is not MessageRole.MEMORY for message in provider.contexts[0]
    )
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.memory_read_failed is True


def test_conversation_reports_isolated_memory_capture_failure() -> None:
    class FailingCapture:
        def capture(self, _user_text: str) -> MemoryCaptureResult:
            return MemoryCaptureResult(failed=True)

    provider = RecordingReplyProvider((("正常回复",),))
    conversation = ConversationService(
        provider,
        build_character(),
        memory_capture=FailingCapture(),
    )

    assert conversation.respond("我喜欢蓝色。") == "正常回复"
    assert conversation.last_metrics is not None
    assert conversation.last_metrics.memory_capture_failed is True
