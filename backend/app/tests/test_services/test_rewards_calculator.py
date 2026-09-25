"""Unit tests for the exploration rewards calculator."""

from types import SimpleNamespace
from uuid import uuid4

from app.models.exploration import Exploration
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
