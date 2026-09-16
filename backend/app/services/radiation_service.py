"""Radiation mechanics rules shared by incidents, exploration, and the game loop.

Pure helpers over a dweller model instance: no session, no commits. Callers
persist changes themselves (attribute tracking or ``db_session.add``).
"""

from typing import TYPE_CHECKING

from app.core.enums import OutfitTypeEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.options.races import RaceOption, race_of

if TYPE_CHECKING:
    from app.models.outfit import Outfit

# Irradiated water deals 1% of max health per tick, so every dweller erodes at
# the same relative pace (tanks hold out on absolute HP, not rate). Tanks still
# hit the fixed cap first on paper, but in practice they keep hundreds of
# effective HP long after weaklings collapse to the 1 HP floor — a multi-hour
# total drought has already failed the vault by then.

# Outfit radiation resist is name-derived like SPECIAL bonuses (see
# utils/item_factory.build_outfit): type base, specific names override.
# Values are shares of incoming RAD removed, 0.0-1.0. The hazmat entries are
# forward-compatible until the catalog adds the suits.
OUTFIT_RADIATION_RESIST_BY_TYPE = {
    OutfitTypeEnum.POWER_ARMOR: 0.75,
    OutfitTypeEnum.RARE: 0.25,
    OutfitTypeEnum.LEGENDARY: 0.25,
    OutfitTypeEnum.TIERED: 0.10,
    OutfitTypeEnum.COMMON: 0.0,
}
OUTFIT_RADIATION_RESIST_BY_NAME = {
    "hazmat suit": 1.0,
    "advanced hazmat suit": 1.0,
}


def outfit_radiation_resist(outfit: "Outfit | None") -> float:
    """Share of incoming RAD an equipped outfit removes. Pure: pass an already-loaded outfit or None, never queries."""
    if outfit is None:
        return 0.0
    by_name = OUTFIT_RADIATION_RESIST_BY_NAME.get(str(getattr(outfit, "name", "")).lower())
    if by_name is not None:
        return by_name
    return OUTFIT_RADIATION_RESIST_BY_TYPE.get(getattr(outfit, "outfit_type", None), 0.0)


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


def apply_radiation_gain(dweller: Dweller, amount: int) -> bool:
    """Add radiation to a dweller, capped at the configured maximum.

    Also pulls current health down to the radiation-reduced ceiling, so callers
    only need to persist the dweller afterwards. Returns True if radiation changed.
    Ghouls are immune and never gain radiation.
    """
    if amount <= 0 or dweller.is_dead or race_of(dweller) == RaceOption.GHOUL:
        return False

    # Outfit resist applies to every source (dehydration, incidents,
    # exploration). __dict__ access mirrors Dweller.weapon_type: no lazy IO,
    # missing relationship simply means no resist.
    amount = int(amount * (1.0 - outfit_radiation_resist(dweller.__dict__.get("outfit"))))
    if amount <= 0:
        return False

    old_radiation = dweller.radiation
    old_health = dweller.health
    dweller.radiation = min(game_config.health.max_radiation, old_radiation + amount)
    dweller.health = min(old_health, dweller.effective_max_health)
    return dweller.radiation != old_radiation or dweller.health != old_health
