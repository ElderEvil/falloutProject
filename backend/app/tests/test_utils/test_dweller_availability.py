"""Tests for the shared dweller availability kernel."""

import pytest

from app.core.enums import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.utils.dweller_availability import (
    UNAVAILABLE_STATUSES,
    availability_error,
    available_dweller_conditions,
    is_available,
)


def _make_dweller(**overrides) -> Dweller:
    """Build a plain mature, healthy, idle dweller with optional overrides."""
    defaults = {
        "first_name": "Test",
        "last_name": "Dweller",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "is_adult": True,
        "age_group": AgeGroupEnum.ADULT,
        "health": 100,
        "is_dead": False,
        "is_deleted": False,
        "status": DwellerStatusEnum.IDLE,
    }
    defaults.update(overrides)
    return Dweller(**defaults)


def test_mature_healthy_dweller_passes() -> None:
    assert availability_error(_make_dweller()) is None


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"is_deleted": True}, "dweller is deleted"),
        ({"is_adult": False}, "dweller is not an adult"),
        ({"age_group": AgeGroupEnum.CHILD}, "dweller is not an adult"),
        ({"age_group": AgeGroupEnum.TEEN}, "dweller is not an adult"),
        ({"is_dead": True}, "dweller is dead"),
        ({"status": DwellerStatusEnum.EXPLORING}, "dweller is exploring"),
        ({"status": DwellerStatusEnum.QUESTING}, "dweller is questing"),
        ({"status": DwellerStatusEnum.DEAD}, "dweller is dead"),
    ],
)
def test_availability_error_rejects_unavailable_dwellers(overrides: dict, expected_reason: str) -> None:
    assert availability_error(_make_dweller(**overrides)) == expected_reason


def test_wounded_dweller_rejected_only_when_require_healthy() -> None:
    wounded = _make_dweller(health=0)
    assert availability_error(wounded, require_healthy=True) == "dweller is wounded"
    assert availability_error(wounded) is None


def test_require_healthy_false_accepts_zero_health_dweller() -> None:
    """Quest assignment historically allowed health-0 dwellers; the default keeps that."""
    assert availability_error(_make_dweller(health=0)) is None
    assert is_available(_make_dweller(health=0)) is True


@pytest.mark.parametrize(
    ("overrides", "require_healthy"),
    [
        ({}, False),
        ({}, True),
        ({"health": 0}, False),
        ({"health": 0}, True),
        ({"is_dead": True}, False),
        ({"status": DwellerStatusEnum.EXPLORING}, False),
        ({"is_deleted": True}, False),
        ({"is_adult": False}, False),
    ],
)
def test_is_available_mirrors_availability_error(overrides: dict, require_healthy: bool) -> None:
    dweller = _make_dweller(**overrides)
    assert is_available(dweller, require_healthy=require_healthy) == (
        availability_error(dweller, require_healthy=require_healthy) is None
    )


def test_available_dweller_conditions_counts() -> None:
    assert len(available_dweller_conditions()) == 5
    assert len(available_dweller_conditions(require_healthy=True)) == 6


def test_unavailable_statuses_match_enum_members() -> None:
    assert (
        frozenset({DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD})
        == UNAVAILABLE_STATUSES
    )
