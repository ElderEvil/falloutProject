"""Unit tests for the radiation helpers: outfit resist scope and the saturation cap."""

from unittest.mock import MagicMock

import pytest

from app.core.enums import OutfitTypeEnum
from app.services.radiation_service import apply_radiation_gain, dehydration_rads


def _human(**overrides: object) -> MagicMock:
    dweller = MagicMock()
    dweller.is_dead = False
    dweller.max_health = 100
    dweller.health = 100
    dweller.radiation = 0
    dweller.visual_attributes = {"race": "human"}
    dweller.outfit = None
    for key, value in overrides.items():
        setattr(dweller, key, value)
    type(dweller).effective_max_health = property(lambda self: max(1, self.max_health - self.radiation))
    return dweller


def _outfit(outfit_type: OutfitTypeEnum, name: str) -> MagicMock:
    outfit = MagicMock()
    outfit.outfit_type = outfit_type
    outfit.name = name
    return outfit


def test_external_radiation_is_resisted_by_power_armor() -> None:
    dweller = _human(outfit=_outfit(OutfitTypeEnum.POWER_ARMOR, "T-51d power armor"))

    assert apply_radiation_gain(dweller, 10) is True

    assert dweller.radiation == 2


def test_ingested_radiation_ignores_outfits() -> None:
    dweller = _human(outfit=_outfit(OutfitTypeEnum.POWER_ARMOR, "T-51d power armor"))

    assert apply_radiation_gain(dweller, 10, resisted_by_outfit=False) is True

    assert dweller.radiation == 10


def test_hazmat_blocks_external_radiation_entirely() -> None:
    dweller = _human(outfit=_outfit(OutfitTypeEnum.RARE, "Hazmat suit"))

    assert apply_radiation_gain(dweller, 10) is False

    assert dweller.radiation == 0


def test_radiation_saturates_at_max_health_and_lowers_the_ceiling() -> None:
    dweller = _human(radiation=95)

    assert apply_radiation_gain(dweller, 50, resisted_by_outfit=False) is True

    assert dweller.radiation == 100
    assert dweller.effective_max_health == 1


@pytest.mark.parametrize(
    ("max_health", "ticks", "expected"),
    [
        (100, 1, 1),
        (100, 5, 5),
        (200, 2, 4),
    ],
)
def test_dehydration_rads_scales_with_health_and_ticks(max_health: int, ticks: int, expected: int) -> None:
    assert dehydration_rads(max_health, ticks) == expected
