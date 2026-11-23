"""Radiation and health-restoration rules shared by incidents, exploration and the game
loop; pure helpers over a dweller instance — callers persist changes themselves.
"""

from app.core.enums import DamageChannel
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.utils.damage_reductions import damage_reductions


def radiation_removal_amount(radiation: int, max_health: int) -> int:
    """RAD removed by one RadAway: half the max-health bar, always at least 1 (mirrors the
    original game; scales with max health, not current RAD).
    """
    removal = int(max_health * game_config.health.radaway_removal_percent)
    return min(radiation, max(1, removal))


def stimpack_heal_amount(max_health: int) -> int:
    """HP restored by one Stimpak: a share of max health, always at least 1."""
    return max(1, int(max_health * game_config.health.stimpack_heal_percent))


def apply_health_gain(dweller: Dweller, amount: int) -> int:
    """Heal a dweller, clamped at the radiation-reduced ceiling; returns the new health."""
    dweller.health = min(dweller.effective_max_health, dweller.health + amount)
    return dweller.health


def apply_radiation_gain(
    dweller: Dweller, amount: int, *, resisted_by_outfit: bool = True, team_share: float = 0.0
) -> bool:
    """Add radiation capped at max health, pulling current health down to the radiation-reduced
    ceiling; returns True if radiation changed.

    Ghouls, super mutants and synths are immune. Outfits resist only external radiation;
    irradiated water is ingestion, so that caller passes resisted_by_outfit=False.
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
