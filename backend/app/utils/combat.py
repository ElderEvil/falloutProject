"""Combat power calculation shared by incident and arena combat."""

from app.core.game_config import game_config
from app.models.dweller import Dweller

UNARMED = "unarmed"


def combat_power(dweller: Dweller) -> float:
    """Total combat power of a single dweller: weapon-type-weighted SPECIAL + weapon damage + level bonus."""
    weapon_type = dweller.weapon.weapon_type.value if dweller.weapon else UNARMED
    weights = game_config.combat.weapon_stat_weights.get(weapon_type) or game_config.combat.weapon_stat_weights[UNARMED]
    stat_power = sum(getattr(dweller, stat) * weight for stat, weight in weights.items())
    weapon_damage = 0
    if dweller.weapon:
        weapon_damage = (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2
    level_bonus = dweller.level * game_config.combat.level_bonus_multiplier
    return stat_power + weapon_damage + level_bonus


def total_combat_power(dwellers: list[Dweller]) -> float:
    """Total combat power across multiple dwellers (incident defender strength)."""
    return sum(combat_power(dweller) for dweller in dwellers)
