"""Combat power calculation shared by incident and arena combat."""

from dataclasses import dataclass

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.options.identity_modifiers import effective_stat, weapon_damage_pct

UNARMED = "unarmed"


@dataclass(frozen=True)
class ExpeditionCombatProfile:
    """Live combat inputs for an exploring dweller."""

    strength: int
    agility: int
    endurance: int
    weapon_damage: float


def expedition_combat_profile(dweller: Dweller) -> ExpeditionCombatProfile:
    """Live combat inputs: effective SPECIAL (identity + equipped outfit) + equipped weapon average damage."""
    weapon = dweller.weapon
    damage = ((weapon.damage_min + weapon.damage_max) / 2) if weapon else 0.0
    return ExpeditionCombatProfile(
        strength=effective_stat(dweller, "strength"),
        agility=effective_stat(dweller, "agility"),
        endurance=effective_stat(dweller, "endurance"),
        weapon_damage=damage,
    )


def combat_power(dweller: Dweller) -> float:
    """Total combat power of a single dweller: weapon-type-weighted SPECIAL + weapon damage + level bonus."""
    weapon_type = dweller.weapon.weapon_type.value if dweller.weapon else UNARMED
    weights = game_config.combat.weapon_stat_weights.get(weapon_type) or game_config.combat.weapon_stat_weights[UNARMED]
    stat_power = sum(effective_stat(dweller, stat) * weight for stat, weight in weights.items())
    weapon_damage = 0
    if dweller.weapon:
        average_damage = (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2
        weapon_damage = average_damage * (1 + weapon_damage_pct(dweller, weapon_type))
    level_bonus = dweller.level * game_config.combat.level_bonus_multiplier
    return stat_power + weapon_damage + level_bonus


def total_combat_power(dwellers: list[Dweller]) -> float:
    """Total combat power across multiple dwellers (incident defender strength)."""
    return sum(combat_power(dweller) for dweller in dwellers)
