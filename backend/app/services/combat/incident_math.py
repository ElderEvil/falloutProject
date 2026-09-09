"""Pure combat math for incidents: power, damage, suppression, and loot rolls."""

import random

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.incident import IncidentType
from app.utils.combat import total_combat_power


def dweller_combat_power(dwellers: list[Dweller]) -> float:
    """Calculate total combat power of dwellers."""
    return total_combat_power(dwellers)


def raider_power(difficulty: int) -> float:
    """Calculate raider power based on difficulty."""
    return difficulty * game_config.combat.base_raider_power


def damage_to_dwellers(raider_power: float, seconds: int) -> float:
    """Calculate damage dealt to dwellers per tick."""
    # Damage reduced by number of dwellers (distributed)
    damage_per_second = raider_power / 10  # Raiders deal 10% of their power per second
    return damage_per_second * seconds


def damage_to_raiders(dweller_power: float, seconds: int) -> float:
    """Calculate damage dealt to raiders per tick."""
    damage_per_second = dweller_power / 5  # Dwellers deal 20% of their power per second
    return damage_per_second * seconds


def fire_damage(hazard_power: float, seconds: int) -> float:
    """Fire harms occupants more slowly than an armed attack."""
    return hazard_power / 20 * seconds


def fire_suppression(dweller_power: float, hazard_power: float, seconds: int) -> float:
    """Return fractional containment progress, where one fully extinguishes a fire."""
    return dweller_power / max(1, hazard_power) * seconds / 5


def generate_loot(difficulty: int, incident_type: IncidentType) -> dict:
    """Generate loot rewards based on difficulty and incident type."""
    caps = random.randint(
        game_config.combat.loot_caps_min + (difficulty - 1) * game_config.combat.loot_caps_max_per_difficulty // 2,
        game_config.combat.loot_caps_min + difficulty * game_config.combat.loot_caps_max_per_difficulty,
    )

    # Internal threats (fire, radroach, mole rat, radscorpion) give caps only
    # External threats (raider, deathclaw, feral ghoul) give caps + items
    internal_threats = {
        IncidentType.FIRE,
        IncidentType.RADROACH_INFESTATION,
        IncidentType.MOLE_RAT_ATTACK,
        IncidentType.RADSCORPION_ATTACK,
    }

    if incident_type in internal_threats:
        # Internal threats: caps only, no items
        return {"caps": caps, "items": []}

    # External threats: caps + weapons/junk based on difficulty
    items = []
    if difficulty >= 7:
        items.append({"type": "weapon", "rarity": "rare", "name": "Heavy Raider Rifle"})
    elif difficulty >= 4:
        items.append({"type": "weapon", "rarity": "uncommon", "name": "Raider Pistol"})
    else:
        items.append({"type": "junk", "name": "Scrap Metal", "quantity": random.randint(1, 3)})

    return {"caps": caps, "items": items}
