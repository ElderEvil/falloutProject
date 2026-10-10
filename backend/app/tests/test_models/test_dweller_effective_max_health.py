"""Dweller ``effective_max_health`` pet-bonus tests (Phase B3).

The ORM property is the mechanics source of truth: medical, radiation, combat
and happiness all consume it. The equipped pet's ``max_health`` effect must be
included, and the ``max(1, ...)`` floor must survive even with a pet equipped.
"""

from app.models.dweller import Dweller
from app.models.pet import Pet
from app.options.pet_modifiers import PET_EFFECT_BY_NAME


def _dweller(max_health: int = 100, radiation: int = 40) -> Dweller:
    return Dweller(
        first_name="Casey",
        last_name="Jones",
        gender="female",
        rarity="common",
        max_health=max_health,
        radiation=radiation,
    )


def test_effective_max_health_includes_equipped_pet_bonus() -> None:
    dweller = _dweller()
    dweller.pet = Pet(name="Dogmeat (Fallout 4)", rarity="Legendary")
    pet_bonus = PET_EFFECT_BY_NAME["dogmeat (fallout 4)"].max_health
    assert dweller.effective_max_health == max(1, 100 + pet_bonus - 40)


def test_effective_max_health_unchanged_without_pet() -> None:
    dweller = _dweller()
    assert dweller.effective_max_health == max(1, 100 - 40)


def test_effective_max_health_floor_still_applies_with_pet() -> None:
    dweller = _dweller(max_health=10, radiation=100)
    dweller.pet = Pet(name="St. Bernard", rarity="Legendary")
    assert dweller.effective_max_health == 1
