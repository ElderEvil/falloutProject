"""Tests for the shared dweller availability kernel."""

import pytest

from app.core.enums import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.utils.dweller_availability import (
    UNAVAILABLE_STATUSES,
    DwellerAction,
    availability_error,
    available_dweller_conditions,
    is_available,
    is_incident_responder_available,
    purposeful_action_error,
)


def _make_dweller(**overrides) -> Dweller:
    """Build a plain mature, healthy, idle dweller with optional overrides."""
    defaults = {
        "first_name": "Test",
        "last_name": "Dweller",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "health": 100,
        "is_dead": False,
        "is_deleted": False,
        "status": DwellerStatusEnum.IDLE,
        "visual_attributes": {"race": "human"},
    }
    defaults.update(overrides)
    return Dweller(**defaults)


def test_mature_healthy_dweller_passes() -> None:
    assert availability_error(_make_dweller()) is None


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"is_deleted": True}, "dweller is deleted"),
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
    ],
)
def test_is_available_mirrors_availability_error(overrides: dict, require_healthy: bool) -> None:
    dweller = _make_dweller(**overrides)
    assert is_available(dweller, require_healthy=require_healthy) == (
        availability_error(dweller, require_healthy=require_healthy) is None
    )


@pytest.mark.parametrize(
    "action",
    [DwellerAction.WORK, DwellerAction.TRAIN, DwellerAction.EXPLORE, DwellerAction.SOCIAL],
)
def test_feral_ghouls_cannot_take_reasoning_actions(action: DwellerAction) -> None:
    feral = _make_dweller(visual_attributes={"race": "ghoul", "state_of_being": "feral"})
    assert purposeful_action_error(feral, action) == "dweller cannot take purposeful actions"


def test_behemoths_cannot_take_reasoning_actions() -> None:
    behemoth = _make_dweller(visual_attributes={"race": "super_mutant", "state_of_being": "behemoth"})
    assert purposeful_action_error(behemoth, DwellerAction.WORK) == "dweller cannot take purposeful actions"


def test_feral_ghouls_and_behemoths_may_fight() -> None:
    feral = _make_dweller(visual_attributes={"race": "ghoul", "state_of_being": "feral"})
    behemoth = _make_dweller(visual_attributes={"race": "super_mutant", "state_of_being": "behemoth"})
    assert purposeful_action_error(feral, DwellerAction.FIGHT) is None
    assert purposeful_action_error(behemoth, DwellerAction.FIGHT) is None
    assert availability_error(feral, action=DwellerAction.FIGHT, require_healthy=True) is None
    assert is_incident_responder_available(feral) is True
    assert is_incident_responder_available(behemoth) is True


def test_feral_ghouls_are_not_available_for_work_or_exploration() -> None:
    feral = _make_dweller(visual_attributes={"race": "ghoul", "state_of_being": "feral"})
    assert availability_error(feral) == "dweller cannot take purposeful actions"
    assert availability_error(feral, action=DwellerAction.EXPLORE) == "dweller cannot take purposeful actions"


@pytest.mark.parametrize("action", [DwellerAction.TRAIN, DwellerAction.FIGHT, DwellerAction.SOCIAL])
def test_children_remain_age_blocked(action: DwellerAction) -> None:
    child = _make_dweller(age_group=AgeGroupEnum.CHILD)
    assert purposeful_action_error(child, action) == "dweller is not an adult"


def test_available_dweller_conditions_counts() -> None:

    assert len(available_dweller_conditions()) == 4
    assert len(available_dweller_conditions(require_healthy=True)) == 5


def test_unavailable_statuses_match_enum_members() -> None:
    assert (
        frozenset({DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD})
        == UNAVAILABLE_STATUSES
    )
