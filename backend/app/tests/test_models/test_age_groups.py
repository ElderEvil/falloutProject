"""Age-group maturity rules shared by the gameplay eligibility gates."""

import pytest

from app.core.enums import ADULT_AGE_GROUPS, AgeGroupEnum
from app.models.dweller import Dweller


def _dweller(age_group: AgeGroupEnum, is_adult: bool = True) -> Dweller:
    return Dweller(
        first_name="Casey",
        last_name="Jones",
        gender="female",
        rarity="common",
        age_group=age_group,
        is_adult=is_adult,
    )


def test_adult_age_groups_covers_adults_and_elders_only() -> None:
    """Elders are grown-ups; children and teens are excluded."""
    assert {AgeGroupEnum.ADULT, AgeGroupEnum.ELDER} == ADULT_AGE_GROUPS


@pytest.mark.parametrize(
    ("age_group", "expected"),
    [
        (AgeGroupEnum.CHILD, False),
        (AgeGroupEnum.TEEN, False),
        (AgeGroupEnum.ADULT, True),
        (AgeGroupEnum.ELDER, True),
    ],
)
def test_is_mature_follows_age_group(age_group: AgeGroupEnum, expected: bool) -> None:
    """Work, combat and exploration eligibility includes elders."""
    assert _dweller(age_group).is_mature is expected


def test_is_mature_still_requires_the_adult_flag() -> None:
    """The age group alone cannot mark a dweller mature."""
    assert _dweller(AgeGroupEnum.ELDER, is_adult=False).is_mature is False


def test_elder_is_a_valid_age_group_value() -> None:
    """The enum member round-trips from its persisted value."""
    assert AgeGroupEnum("elder") is AgeGroupEnum.ELDER
