import pytest

from atosaac_virtual_partner.context import (
    FullHistoryContextPolicy,
    RecentTurnsContextPolicy,
)
from atosaac_virtual_partner.message import Message, MessageRole


def build_history(turn_count: int) -> tuple[Message, ...]:
    return tuple(
        message
        for turn in range(1, turn_count + 1)
        for message in (
            Message(MessageRole.USER, f"user {turn}"),
            Message(MessageRole.ASSISTANT, f"assistant {turn}"),
        )
    )


def test_full_history_policy_is_a_compatibility_fallback() -> None:
    history = build_history(3)

    assert FullHistoryContextPolicy().select_history(history) == history


def test_recent_turns_policy_keeps_newest_complete_turns() -> None:
    history = build_history(4)

    selected = RecentTurnsContextPolicy(max_turns=2).select_history(history)

    assert selected == build_history(4)[-4:]
    assert selected[0] == Message(MessageRole.USER, "user 3")


def test_recent_turns_policy_keeps_all_history_below_limit() -> None:
    history = build_history(2)

    assert RecentTurnsContextPolicy(max_turns=8).select_history(history) == history


def test_recent_turns_policy_does_not_mutate_complete_history() -> None:
    history = list(build_history(3))

    RecentTurnsContextPolicy(max_turns=1).select_history(history)

    assert history == list(build_history(3))


@pytest.mark.parametrize("max_turns", (0, -1, True, 1.5))
def test_recent_turns_policy_rejects_invalid_limits(max_turns: object) -> None:
    with pytest.raises(ValueError, match="max_turns"):
        RecentTurnsContextPolicy(max_turns=max_turns)  # type: ignore[arg-type]


def test_recent_turns_policy_rejects_invalid_history_boundaries() -> None:
    invalid_history = (Message(MessageRole.ASSISTANT, "orphan reply"),)

    with pytest.raises(ValueError, match="start with a user"):
        RecentTurnsContextPolicy().select_history(invalid_history)


def test_recent_turns_policy_rejects_system_messages_in_history() -> None:
    invalid_history = (
        Message(MessageRole.USER, "hello"),
        Message(MessageRole.SYSTEM, "unexpected policy"),
    )

    with pytest.raises(ValueError, match="system messages"):
        RecentTurnsContextPolicy().select_history(invalid_history)


def test_recent_turns_policy_treats_application_event_as_a_turn_start() -> None:
    history = (
        Message(MessageRole.USER, "user 1"),
        Message(MessageRole.ASSISTANT, "assistant 1"),
        Message(MessageRole.EVENT, "idle event"),
        Message(MessageRole.ASSISTANT, "initiative 1"),
    )

    selected = RecentTurnsContextPolicy(max_turns=1).select_history(history)

    assert selected == history[-2:]
