"""Radiation mechanics rules shared by incidents, exploration, and the game loop.

Pure helpers over a dweller model instance: no session, no commits. Callers
persist changes themselves (attribute tracking or ``db_session.add``).
"""

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.options.races import RaceOption, race_of


def radiation_removal_amount(radiation: int) -> int:
    """RAD removed by one RadAway: a share of current radiation, always at least 1."""
    removal = int(radiation * game_config.health.radaway_removal_percent)
    return min(radiation, max(1, removal))


def apply_radiation_gain(dweller: Dweller, amount: int) -> bool:
    """Add radiation to a dweller, capped at the configured maximum.

    Also pulls current health down to the radiation-reduced ceiling, so callers
    only need to persist the dweller afterwards. Returns True if radiation changed.
    Ghouls are immune and never gain radiation.
    """
    if amount <= 0 or dweller.is_dead or race_of(dweller) == RaceOption.GHOUL:
        return False

    old_radiation = dweller.radiation
    old_health = dweller.health
    dweller.radiation = min(game_config.health.max_radiation, old_radiation + amount)
    dweller.health = min(old_health, dweller.effective_max_health)
    return dweller.radiation != old_radiation or dweller.health != old_health
