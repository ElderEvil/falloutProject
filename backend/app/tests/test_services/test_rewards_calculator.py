"""Unit tests for the exploration rewards calculator."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.core.enums import RarityEnum
from app.models.exploration import Exploration
from app.models.pet import Pet
from app.options.pet_modifiers import MAX_PCT_BONUS, PetEffect
from app.services.exploration.rewards_calculator import rewards_calculator


def _exploration(events: list[dict]) -> Exploration:
    return Exploration(
        vault_id=uuid4(),
        dweller_id=uuid4(),
        duration=4,
        dweller_strength=5,
        dweller_perception=5,
        dweller_endurance=5,
        dweller_charisma=5,
        dweller_intelligence=5,
        dweller_agility=5,
        dweller_luck=5,
        events=events,
    )


def _dweller(pet: Pet | None = None) -> SimpleNamespace:
    return SimpleNamespace(health=100, effective_max_health=100, pet=pet)


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity=RarityEnum.RARE)


def test_site_events_excluded_from_event_xp():
    """Site events are journey-log noise; only non-site events earn event XP."""
    dweller = SimpleNamespace(health=100, effective_max_health=100)
    base = _exploration(events=[{"type": "random", "description": "Found a cache"}])
    with_site = _exploration(
        events=[
            {"type": "random", "description": "Found a cache"},
            {"type": "site", "description": "Entered Red Rocket"},
            {"type": "site", "description": "Garage: Overpowered by Mole Rat pack!"},
        ]
    )
    assert rewards_calculator.calculate_exploration_xp(
        with_site, dweller
    ) == rewards_calculator.calculate_exploration_xp(base, dweller)


def test_pet_xp_bonus_included():
    """A pet with xp_pct adds an additive percentage of base XP."""
    exploration = _exploration(events=[{"type": "random", "description": "Found a cache"}])
    exploration.total_distance = 100

    base = rewards_calculator.calculate_exploration_xp(exploration, _dweller())
    with_pet = rewards_calculator.calculate_exploration_xp(exploration, _dweller(_pet("CX404")))

    # cx404 grants +25% of base XP (100 miles * 10 + 1 event * 20 = 1020).
    assert with_pet - base == int(1020 * 0.25)


def test_pet_xp_bonus_capped_at_max_pct():
    """xp_pct above MAX_PCT_BONUS is clamped to the cap."""
    exploration = _exploration(events=[{"type": "random", "description": "Found a cache"}])
    exploration.total_distance = 100

    with patch(
        "app.services.exploration.rewards_calculator.pet_modifiers_for",
        return_value=PetEffect(xp_pct=0.8),
    ):
        capped = rewards_calculator.calculate_exploration_xp(exploration, _dweller())

    base = rewards_calculator.calculate_exploration_xp(exploration, _dweller())
    assert capped - base == int(1020 * MAX_PCT_BONUS)


def test_no_pet_xp_unchanged():
    """A dweller without an equipped pet earns the same XP as before pets."""
    exploration = _exploration(events=[{"type": "random", "description": "Found a cache"}])
    exploration.total_distance = 100

    # base 1020 + survival 204 + luck 102 (5 luck * 2%) — no pet term.
    assert rewards_calculator.calculate_exploration_xp(exploration, _dweller()) == 1326
