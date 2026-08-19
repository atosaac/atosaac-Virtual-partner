import pytest

from atosaac_virtual_partner.initiative import IdleInitiativePolicy


def test_idle_initiative_allows_only_configured_consecutive_turns() -> None:
    policy = IdleInitiativePolicy(idle_seconds=60, max_without_user_activity=1)

    assert policy.can_trigger(0) is True
    assert policy.can_trigger(1) is False
    assert "不是用户说的话" in policy.event_instructions()
    assert "不要提到计时器" in policy.event_instructions()
    assert "不要编造" in policy.event_instructions()
    assert "不要问“最近在忙什么”" in policy.event_instructions()


@pytest.mark.parametrize("idle_seconds", (0, -1, True, float("inf")))
def test_idle_initiative_rejects_invalid_timeout(idle_seconds: object) -> None:
    with pytest.raises(ValueError, match="idle_seconds"):
        IdleInitiativePolicy(idle_seconds=idle_seconds)  # type: ignore[arg-type]


@pytest.mark.parametrize("maximum", (0, -1, True, 1.5))
def test_idle_initiative_rejects_invalid_maximum(maximum: object) -> None:
    with pytest.raises(ValueError, match="maximum"):
        IdleInitiativePolicy(
            idle_seconds=60,
            max_without_user_activity=maximum,  # type: ignore[arg-type]
        )
