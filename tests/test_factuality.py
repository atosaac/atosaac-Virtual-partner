from atosaac_virtual_partner.factuality import (
    GroundingAudit,
    GroundingRisk,
    HeuristicReplyGroundingAuditor,
)
from atosaac_virtual_partner.message import Message, MessageRole


def audit(reply_text: str, user_text: str = "普通聊天") -> GroundingAudit:
    return HeuristicReplyGroundingAuditor().audit(
        reply_text,
        (Message(MessageRole.USER, user_text),),
    )


def test_auditor_flags_unsupported_memory_claim() -> None:
    result = audit("你上次煮的那锅粥，我到现在还记得。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_MEMORY,)


def test_auditor_accepts_prior_event_grounded_by_user() -> None:
    result = audit(
        "你上次煮的那锅粥，我到现在还记得。",
        user_text="我上次把粥煮糊了。",
    )

    assert result.risks == ()


def test_auditor_does_not_treat_a_question_as_memory_evidence() -> None:
    result = audit(
        "你上次确实把粥煮糊了。",
        user_text="我以前是不是把粥煮糊过？",
    )

    assert result.risks == (GroundingRisk.UNSUPPORTED_MEMORY,)


def test_auditor_flags_unsupported_remote_perception() -> None:
    result = audit("你房间的灯还亮着，我刚才偷偷看了一眼。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_PERCEPTION,)


def test_auditor_accepts_explicit_perception_limit() -> None:
    result = audit("我不能看见你房间的灯。")

    assert result.risks == ()


def test_auditor_flags_unframed_physical_state() -> None:
    result = audit("我刚睡醒，眼睛还没睁开。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_PHYSICAL_STATE,)


def test_later_uncertainty_does_not_reframe_a_physical_claim() -> None:
    result = audit("我刚睡醒，可能反应有点慢。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_PHYSICAL_STATE,)


def test_auditor_preserves_explicit_future_imagination() -> None:
    result = audit(
        "十年后的我可能早就学会煮泡面了。",
        user_text="那十年后的你呢？",
    )

    assert result.risks == ()


def test_auditor_does_not_treat_future_memory_as_past_claim() -> None:
    result = audit(
        "十年后的我说不定还会记得现在。",
        user_text="那十年后的你呢？",
    )

    assert result.risks == ()


def test_auditor_flags_invented_self_history() -> None:
    result = audit("就像我第一次写代码，后来才慢慢学会。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_SELF_HISTORY,)


def test_auditor_preserves_hypothetical_self_history() -> None:
    result = audit("假如我第一次写代码，大概会先被报错吓一跳。")

    assert result.risks == ()


def test_current_chat_perception_is_not_self_history() -> None:
    result = audit("我第一次看到你这样形容。")

    assert result.risks == ()


def test_imaginative_comparison_does_not_excuse_remote_perception() -> None:
    result = audit("你房间的灯还亮着，像是在等谁。")

    assert result.risks == (GroundingRisk.UNSUPPORTED_PERCEPTION,)


def test_reading_visible_chat_text_is_not_remote_perception() -> None:
    result = audit("我看到你这句话就笑了。")

    assert result.risks == ()
