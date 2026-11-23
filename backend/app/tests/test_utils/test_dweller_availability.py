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

NON_REASONING_RACES = {
    "feral": {"race": "ghoul", "state_of_being": "feral"},
    "behemoth": {"race": "super_mutant", "state_of_being": "behemoth"},
}
AVAILABILITY_CASES = [
    ({}, False, None),
    ({}, True, None),
    ({"is_deleted": True}, False, "dweller is deleted"),
    ({"age_group": AgeGroupEnum.CHILD}, False, "dweller is not an adult"),
    ({"age_group": AgeGroupEnum.TEEN}, False, "dweller is not an adult"),
    ({"is_dead": True}, False, "dweller is dead"),
    ({"status": DwellerStatusEnum.EXPLORING}, False, "dweller is exploring"),
    ({"status": DwellerStatusEnum.QUESTING}, False, "dweller is questing"),
    ({"status": DwellerStatusEnum.DEAD}, False, "dweller is dead"),
    ({"health": 0}, False, None),
    ({"health": 0}, True, "dweller is wounded"),
]


def _make_dweller(**overrides) -> Dweller:
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
    return Dweller(**(defaults | overrides))


@pytest.mark.parametrize(("overrides", "require_healthy", "expected"), AVAILABILITY_CASES)
def test_availability_and_is_available(overrides: dict, require_healthy: bool, expected: str | None) -> None:
    dweller = _make_dweller(**overrides)
    assert availability_error(dweller, require_healthy=require_healthy) == expected
    assert is_available(dweller, require_healthy=require_healthy) == (expected is None)


@pytest.mark.parametrize("race", list(NON_REASONING_RACES))
def test_feral_ghouls_and_behemoths_action_rules(race: str) -> None:
    dweller = _make_dweller(visual_attributes=NON_REASONING_RACES[race])
    for action in (DwellerAction.WORK, DwellerAction.TRAIN, DwellerAction.EXPLORE, DwellerAction.SOCIAL):
        assert purposeful_action_error(dweller, action) == "dweller cannot take purposeful actions"
    assert purposeful_action_error(dweller, DwellerAction.FIGHT) is None
    assert availability_error(dweller) == "dweller cannot take purposeful actions"
    assert availability_error(dweller, action=DwellerAction.EXPLORE) == "dweller cannot take purposeful actions"
    assert availability_error(dweller, action=DwellerAction.FIGHT, require_healthy=True) is None
    assert is_incident_responder_available(dweller) is True


@pytest.mark.parametrize("action", [DwellerAction.TRAIN, DwellerAction.FIGHT, DwellerAction.SOCIAL])
def test_children_remain_age_blocked(action: DwellerAction) -> None:
    child = _make_dweller(age_group=AgeGroupEnum.CHILD)
    assert purposeful_action_error(child, action) == "dweller is not an adult"


def test_available_dweller_conditions_and_statuses() -> None:
    assert len(available_dweller_conditions()) == 4
    assert len(available_dweller_conditions(require_healthy=True)) == 5
    assert frozenset({DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD}) == (
        UNAVAILABLE_STATUSES
    )
