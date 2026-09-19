"""Outfit protection against vault hazards.

Pure helpers over an already-loaded outfit: no session, no lazy IO. Both hazard
channels (fire and radiation) read their outfit share here, so the damage
resolver (``utils/damage_reductions.py``) has one home for outfit resists.
"""

from typing import TYPE_CHECKING

from app.core.enums import OutfitTypeEnum

if TYPE_CHECKING:
    from app.models.outfit import Outfit


def outfit_fire_resist(outfit: "Outfit | None") -> float:
    """Share of fire damage an equipped outfit removes."""
    if outfit is None:
        return 0.0
    return float(getattr(outfit, "fire_resist", 0.0) or 0.0)


# Outfit radiation resist is name-derived like SPECIAL bonuses (see
# utils/item_factory.build_outfit): type base, specific names override.
# Values are shares of incoming RAD removed, 0.0-1.0. Only power armor (by
# type) and hazmat suits (by name) grant rad resist; other outfits get none
# unless they declare radiation_resist.
OUTFIT_RADIATION_RESIST_BY_TYPE = {
    OutfitTypeEnum.POWER_ARMOR: 0.75,
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
    declared = getattr(outfit, "radiation_resist", None)
    if declared is not None:
        return float(declared)
    by_name = OUTFIT_RADIATION_RESIST_BY_NAME.get(str(getattr(outfit, "name", "")).lower())
    if by_name is not None:
        return by_name
    return OUTFIT_RADIATION_RESIST_BY_TYPE.get(getattr(outfit, "outfit_type", None), 0.0)
