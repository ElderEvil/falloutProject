"""Tests for quest duration helpers, including the return leg."""

from app.utils.quest_duration import (
    QUEST_RETURN_LEG_FRACTION,
    QUEST_RETURN_LEG_MAX_MINUTES,
    effective_quest_duration_minutes,
    quest_return_leg_minutes,
)


def test_return_leg_is_half_the_effective_duration() -> None:
    """The trip home lasts half the quest's effective duration."""
    assert QUEST_RETURN_LEG_FRACTION == 0.5
    assert quest_return_leg_minutes(40) == 20
    assert quest_return_leg_minutes(60) == 30


def test_return_leg_is_capped_at_thirty_minutes() -> None:
    """A long quest never adds more than 30 minutes of travel time."""
    assert QUEST_RETURN_LEG_MAX_MINUTES == 30
    assert quest_return_leg_minutes(240) == 30
    assert quest_return_leg_minutes(120) == 30


def test_return_leg_has_a_one_minute_floor() -> None:
    """Even a one-minute quest keeps a one-minute return leg."""
    assert quest_return_leg_minutes(1) == 1
    assert quest_return_leg_minutes(2) == 1


def test_return_leg_inherits_the_test_duration_multiplier(monkeypatch) -> None:
    """The return leg derives from the effective duration, so the test multiplier shrinks it too."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "QUEST_DURATION_MULTIPLIER", 0.2)
    effective = effective_quest_duration_minutes(240)
    assert effective == 48
    assert quest_return_leg_minutes(effective) == 24
