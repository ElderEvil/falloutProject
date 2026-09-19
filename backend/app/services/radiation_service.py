"""Radiation mechanics rules shared by incidents, exploration, and the game loop.

Pure helpers over a dweller model instance: no session, no commits. Callers
persist changes themselves (attribute tracking or ``db_session.add``).
"""

from app.core.enums import DamageChannel
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.utils.damage_reductions import damage_reductions

# Irradiated water deals 1% of max health per tick, so every dweller erodes at
# the same relative pace (tanks hold out on absolute HP, not rate). Tanks still
# hit the fixed cap first on paper, but in practice they keep hundreds of
# effective HP long after weaklings collapse to the 1 HP floor — a multi-hour
# total drought has already failed the vault by then.


def dehydration_rads(max_health: int, ticks: int) -> int:
    """Raw irradiated-water RAD for a tick span: 1% of max HP per tick, scaled by elapsed ticks."""
    return max(1, int(max_health * game_config.health.dehydration_percent_per_tick * ticks))


def radiation_removal_amount(radiation: int, max_health: int) -> int:
    """RAD removed by one RadAway: a share of max health, always at least 1.

    Mirrors the original game: one dose clears half the health bar of red,
    so it scales with the dweller's max health rather than current RAD.
    """
    removal = int(max_health * game_config.health.radaway_removal_percent)
    return min(radiation, max(1, removal))


def apply_radiation_gain(
    dweller: Dweller, amount: int, *, resisted_by_outfit: bool = True, team_share: float = 0.0
) -> bool:
    """Add radiation to a dweller, capped at max health.

    Also pulls current health down to the radiation-reduced ceiling, so callers
    only need to persist the dweller afterwards. Returns True if radiation changed.
    Ghouls are immune and never gain radiation.

    Outfits only resist **external** radiation (incidents, wasteland events).
    Radiation drunk as irradiated water enters through ingestion, so that caller
    passes ``resisted_by_outfit=False`` and armor cannot block it.
    """
    if amount <= 0 or dweller.is_dead:
        return False

    reductions = damage_reductions(
        dweller, DamageChannel.RADIATION, team_share=team_share, resisted_by_outfit=resisted_by_outfit
    )
    amount = reductions.apply(amount)
    if amount <= 0:
        return False

    old_radiation = dweller.radiation
    old_health = dweller.health
    dweller.radiation = min(dweller.max_health, old_radiation + amount)
    dweller.health = min(old_health, dweller.effective_max_health)
    return dweller.radiation != old_radiation or dweller.health != old_health
