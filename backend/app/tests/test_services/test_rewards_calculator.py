from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.core.enums import RarityEnum
from app.models.exploration import Exploration
from app.models.pet import Pet
from app.options.pet_modifiers import MAX_PCT_BONUS, PetEffect
from app.services.exploration.rewards_calculator import rewards_calculator

_cache = [{"type": "random", "description": "Found a cache"}]


def _exploration(events: list[dict], distance: int = 0, location_xp: int | None = None) -> Exploration:
    special = {"strength": 5, "perception": 5, "endurance": 5, "charisma": 5, "intelligence": 5, "agility": 5}
    exploration = Exploration(
        vault_id=uuid4(),
        dweller_id=uuid4(),
        duration=4,
        events=events,
        dweller_luck=5,
        **{f"dweller_{key}": value for key, value in special.items()},
    )
    exploration.total_distance, exploration.location_xp = distance, location_xp
    return exploration


def _dweller(pet: Pet | None = None) -> SimpleNamespace:
    return SimpleNamespace(health=100, effective_max_health=100, pet=pet)


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity=RarityEnum.RARE)


def test_site_events_excluded_from_event_xp():
    base = _exploration(_cache)
    with_site = _exploration(
        [
            *_cache,
            {"type": "site", "description": "Entered Red Rocket"},
            {"type": "site", "description": "Garage: Overpowered by Mole Rat pack!"},
        ]
    )
    assert rewards_calculator.calculate_exploration_xp(with_site, _dweller()) == (
        rewards_calculator.calculate_exploration_xp(base, _dweller())
    )


def test_pet_xp_bonus_included():
    exploration = _exploration(_cache, distance=100)
    base = rewards_calculator.calculate_exploration_xp(exploration, _dweller())
    with_pet = rewards_calculator.calculate_exploration_xp(exploration, _dweller(_pet("CX404")))
    # cx404 grants +25% of base XP (100 miles * 10 + 1 event * 20 = 1020).
    assert with_pet - base == int(1020 * 0.25)


def test_pet_xp_bonus_capped_at_max_pct():
    exploration = _exploration(_cache, distance=100)
    with patch(
        "app.services.exploration.rewards_calculator.pet_modifiers_for",
        return_value=PetEffect(xp_pct=0.8),
    ):
        capped = rewards_calculator.calculate_exploration_xp(exploration, _dweller())
    base = rewards_calculator.calculate_exploration_xp(exploration, _dweller())
    assert capped - base == int(1020 * MAX_PCT_BONUS)


@pytest.mark.parametrize(
    ("distance", "location_xp", "expected"),
    [
        pytest.param(100, None, 1326, id="distance-and-event"),
        pytest.param(0, 100, 130, id="location-xp"),
        pytest.param(0, None, 0, id="no-xp-sources"),
    ],
)
def test_no_pet_xp_is_additive_and_bonus_scaled(distance: int, location_xp: int | None, expected: int):
    # Base + survival 20% + luck 10% (5 luck * 2%); no pet term.
    events = _cache if distance else []
    assert (
        rewards_calculator.calculate_exploration_xp(_exploration(events, distance, location_xp), _dweller()) == expected
    )
