"""Unit tests for the radiation and health-restoration helpers: outfit resist scope, saturation cap, and stimpack healing."""

from unittest.mock import MagicMock

import pytest

from app.core.enums import OutfitTypeEnum
from app.core.game_config import game_config
from app.services.radiation_service import (
    apply_health_gain,
    apply_radiation_gain,
    dehydration_rads,
    stimpack_heal_amount,
)


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


def _outfit(outfit_type: OutfitTypeEnum, name: str, radiation_resist: float | None = None) -> MagicMock:
    outfit = MagicMock()
    outfit.outfit_type = outfit_type
    outfit.name = name
    # A real outfit row carries either a declared share or NULL; a bare
    # MagicMock would answer the column read with another mock.
    outfit.radiation_resist = radiation_resist
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


def test_plain_rare_outfit_does_not_resist_radiation() -> None:
    """Only power armor (by type) and hazmat suits (by name) resist; a bare
    rare outfit with no declared share grants nothing."""
    dweller = _human(outfit=_outfit(OutfitTypeEnum.RARE, "Metal Armor"))

    assert apply_radiation_gain(dweller, 10) is True

    assert dweller.radiation == 10


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


def test_stimpack_heal_amount_is_share_of_max_health() -> None:
    assert stimpack_heal_amount(100) == max(1, int(100 * game_config.health.stimpack_heal_percent))


@pytest.mark.parametrize("max_health", [1, 2])
def test_stimpack_heal_amount_never_below_one(max_health: int) -> None:
    assert stimpack_heal_amount(max_health) == 1


def test_apply_health_gain_returns_and_sets_new_health() -> None:
    dweller = _human(health=10)

    assert apply_health_gain(dweller, 40) == 50
    assert dweller.health == 50


def test_apply_health_gain_clamps_at_effective_max_health() -> None:
    dweller = _human(health=80)

    assert apply_health_gain(dweller, 50) == 100
    assert dweller.health == 100


def test_apply_health_gain_respects_radiation_reduced_ceiling() -> None:
    dweller = _human(health=30, radiation=40)

    assert apply_health_gain(dweller, 40) == 60
    assert dweller.health == 60


def test_apply_health_gain_with_zero_amount_is_no_change() -> None:
    dweller = _human(health=80)

    assert apply_health_gain(dweller, 0) == 80
    assert dweller.health == 80
