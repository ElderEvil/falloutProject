"""Combat power calculation shared by incident and arena combat."""

from app.core.game_config import game_config
from app.models.dweller import Dweller


def combat_power(dweller: Dweller) -> float:
    """Total combat power of a single dweller: SPECIAL-weighted stats + weapon damage + level bonus."""
    stat_power = (
        dweller.strength * game_config.combat.dweller_strength_weight
        + dweller.endurance * game_config.combat.dweller_endurance_weight
        + dweller.agility * game_config.combat.dweller_agility_weight
    )
    weapon_damage = 0
    if dweller.weapon:
        weapon_damage = (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2
    level_bonus = dweller.level * game_config.combat.level_bonus_multiplier
    return stat_power + weapon_damage + level_bonus


def total_combat_power(dwellers: list[Dweller]) -> float:
    """Total combat power across multiple dwellers (incident defender strength)."""
    return sum(combat_power(dweller) for dweller in dwellers)
