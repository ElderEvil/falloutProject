"""Resolve a dweller's race and faction into one set of mechanical modifiers.

The single reader for identity mechanics: combat, production, radiation and incident
resolution all ask this module instead of branching on race or faction themselves.
Pure and session-free, so game-loop actors and API paths share the same rules.
"""

from dataclasses import dataclass

from app.core.enums import SPECIAL_STATS
from app.core.game_config import game_config
from app.options.factions import FactionPerks, perks_for_faction
from app.options.races import RaceModifiers, modifiers_for_race

#: Weapon types whose faction perk is a damage bonus, keyed by the weapon-type value.
_WEAPON_PERK_FIELDS: dict[str, str] = {
    "energy": "energy_weapon_damage_pct",
    "melee": "melee_damage_pct",
}


@dataclass(frozen=True)
class IdentityModifiers:
    """Combined racial and faction effects for one dweller."""

    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0
    radiation_immune: bool = False
    radiation_resist_pct: float = 0.0
    energy_weapon_damage_pct: float = 0.0
    melee_damage_pct: float = 0.0
    incident_response_pct: float = 0.0
    production_pct: float = 0.0


def _combine(race: RaceModifiers, faction: FactionPerks) -> IdentityModifiers:
    return IdentityModifiers(
        strength=race.strength,
        perception=race.perception,
        endurance=race.endurance,
        charisma=race.charisma,
        intelligence=race.intelligence,
        agility=race.agility,
        luck=race.luck,
        radiation_immune=race.radiation_immune,
        radiation_resist_pct=min(1.0, race.radiation_resist_pct + faction.radiation_resist_pct),
        energy_weapon_damage_pct=faction.energy_weapon_damage_pct,
        melee_damage_pct=faction.melee_damage_pct,
        incident_response_pct=faction.incident_response_pct,
        production_pct=faction.production_pct,
    )


def identity_modifiers_for(entity: object) -> IdentityModifiers:
    """Combined race and faction modifiers for an entity, defaulting to a neutral identity.

    Race and faction are gated separately: ``features.race_mechanics`` covers stat
    deltas and racial resistances, ``features.faction_mechanics`` covers perks.
    Ghoul radiation immunity survives either switch, because it predates both and is
    documented behaviour.
    """
    race = modifiers_for_race(entity)
    if not game_config.features.race_mechanics:
        race = RaceModifiers(radiation_immune=race.radiation_immune)

    faction = perks_for_faction(entity) if game_config.features.faction_mechanics else FactionPerks()
    return _combine(race, faction)


def effective_stat(entity: object, stat: str) -> int:
    """A dweller's stat after identity and equipped-outfit modifiers, floored at 1.

    Derived on read and never persisted: the stored SPECIAL stays the trained value,
    so removing a race, faction, or outfit cannot leave a permanent stat change behind.
    The outfit is read via ``__dict__`` (no lazy IO, a missing relationship means no
    bonus), and the result is not capped — a 10 S dweller in a +5 S outfit counts as 15.
    """
    if stat not in SPECIAL_STATS:
        raise ValueError(f"Unknown SPECIAL stat: {stat!r}")
    outfit = entity.__dict__.get("outfit")
    outfit_bonus = getattr(outfit, stat, 0) if outfit is not None else 0
    return max(1, getattr(entity, stat) + getattr(identity_modifiers_for(entity), stat) + outfit_bonus)


def weapon_damage_pct(entity: object, weapon_type: str) -> float:
    """Faction damage bonus for a weapon type; types without a perk return zero."""
    field = _WEAPON_PERK_FIELDS.get(weapon_type)
    return getattr(identity_modifiers_for(entity), field) if field else 0.0
