"""Pure combat math for incidents: power, damage, suppression, and loot rolls."""

import random
from dataclasses import dataclass

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.incident import IncidentType
from app.utils.combat import total_combat_power
from app.utils.static_data import game_data_store


@dataclass(frozen=True)
class IncidentRewardTier:
    """What an incident type pays out, before difficulty scaling."""

    caps_multiplier: float
    item_kind: str | None = None
    item_rarity: str | None = None
    elite_rarity: str | None = None
    elite_difficulty: int = 7


# Hazards pay in experience; infestations in caps; intrusions in caps and gear,
# escalating to the vault's best salvage.
INCIDENT_REWARD_TIERS: dict[IncidentType, IncidentRewardTier] = {
    IncidentType.FIRE: IncidentRewardTier(caps_multiplier=0.0),
    IncidentType.RADROACH_INFESTATION: IncidentRewardTier(caps_multiplier=0.25),
    IncidentType.MOLE_RAT_ATTACK: IncidentRewardTier(caps_multiplier=0.5),
    IncidentType.RADSCORPION_ATTACK: IncidentRewardTier(caps_multiplier=0.5),
    IncidentType.FERAL_GHOUL_ATTACK: IncidentRewardTier(caps_multiplier=0.6, item_kind="junk", item_rarity="common"),
    IncidentType.RAIDER_ATTACK: IncidentRewardTier(
        caps_multiplier=1.0,
        item_kind="weapon",
        item_rarity="common",
        elite_rarity="rare",
        elite_difficulty=7,
    ),
    IncidentType.DEATHCLAW_ATTACK: IncidentRewardTier(
        caps_multiplier=1.5,
        item_kind="junk",
        item_rarity="rare",
        elite_rarity="legendary",
        elite_difficulty=8,
    ),
}


def get_reward_tier(incident_type: IncidentType) -> IncidentRewardTier:
    """Return the reward tier for an incident type."""
    return INCIDENT_REWARD_TIERS[incident_type]


def _base_caps(difficulty: int) -> int:
    return random.randint(
        game_config.combat.loot_caps_min + (difficulty - 1) * game_config.combat.loot_caps_max_per_difficulty // 2,
        game_config.combat.loot_caps_min + difficulty * game_config.combat.loot_caps_max_per_difficulty,
    )


def _catalog_item(kind: str, rarity: str) -> dict | None:
    """Roll a real catalog item, so granted loot is never a phantom name."""
    pool = game_data_store.junk_items if kind == "junk" else game_data_store.weapons
    candidates = [item for item in pool if str(item.rarity).lower() == rarity.lower()]
    if not candidates:
        return None
    chosen = random.choice(candidates)
    return {"item_type": kind, "rarity": str(chosen.rarity).lower(), "name": chosen.name}


def generate_loot(difficulty: int, incident_type: IncidentType) -> dict:
    """Generate type-tiered loot: difficulty-scaled caps plus a catalog item."""
    tier = get_reward_tier(incident_type)
    caps = int(_base_caps(difficulty) * tier.caps_multiplier)

    items: list[dict] = []
    if tier.item_kind and tier.item_rarity:
        rarity = tier.elite_rarity if tier.elite_rarity and difficulty >= tier.elite_difficulty else tier.item_rarity
        item = _catalog_item(tier.item_kind, rarity)
        if item:
            items.append(item)

    return {"caps": caps, "items": items}


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
