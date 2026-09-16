"""Faction options with race-based restrictions and lore-aligned perks."""

from dataclasses import dataclass
from enum import StrEnum

from app.options.races import RaceOption


class FactionOption(StrEnum):
    """Faction affiliations for character appearance."""

    VAULT_DWELLER = "vault_dweller"
    BROTHERHOOD_OF_STEEL = "brotherhood_of_steel"
    ENCLAVE = "enclave"
    MINUTEMEN = "minutemen"
    RAIDERS = "raiders"
    SUPER_MUTANT_TRIBE = "super_mutant_tribe"
    CHILDREN_OF_ATOM = "children_of_atom"
    THE_INSTITUTE = "the_institute"
    RAILROAD = "railroad"
    NCR = "ncr"
    CAESARS_LEGION = "caesars_legion"
    NONE = "none"


# Which factions are valid for each race
faction_restrictions: dict[RaceOption, list[FactionOption]] = {
    RaceOption.HUMAN: [
        FactionOption.VAULT_DWELLER,
        FactionOption.BROTHERHOOD_OF_STEEL,
        FactionOption.ENCLAVE,
        FactionOption.MINUTEMEN,
        FactionOption.RAIDERS,
        FactionOption.CHILDREN_OF_ATOM,
        FactionOption.THE_INSTITUTE,
        FactionOption.RAILROAD,
        FactionOption.NCR,
        FactionOption.CAESARS_LEGION,
        FactionOption.NONE,
    ],
    RaceOption.GHOUL: [
        FactionOption.VAULT_DWELLER,
        FactionOption.RAIDERS,
        FactionOption.CHILDREN_OF_ATOM,
        FactionOption.NONE,
    ],
    RaceOption.SUPER_MUTANT: [
        FactionOption.SUPER_MUTANT_TRIBE,
        FactionOption.RAIDERS,
        FactionOption.NONE,
    ],
    RaceOption.SYNTH: [
        FactionOption.THE_INSTITUTE,
        FactionOption.RAILROAD,
        FactionOption.NONE,
    ],
}


@dataclass(frozen=True)
class FactionPerks:
    """Faction bonuses, declared beside the faction options.

    Combat perks reuse the weapon-type lookup rather than new formulas, and every
    field is applied somewhere: energy/melee in ``combat_power``, incident response on
    incoming damage, production on room output, radiation resist in the radiation
    helper. No field exists without a consumer.
    """

    energy_weapon_damage_pct: float = 0.0
    melee_damage_pct: float = 0.0
    incident_response_pct: float = 0.0
    production_pct: float = 0.0
    radiation_resist_pct: float = 0.0


#: Faction perks keyed by faction; `none` and the factions without a mechanic yet
#: carry the neutral value instead of a speculative bonus.
FACTION_PERKS: dict[FactionOption, FactionPerks] = {
    FactionOption.VAULT_DWELLER: FactionPerks(production_pct=0.05),
    FactionOption.BROTHERHOOD_OF_STEEL: FactionPerks(energy_weapon_damage_pct=0.15),
    FactionOption.ENCLAVE: FactionPerks(energy_weapon_damage_pct=0.10),
    FactionOption.MINUTEMEN: FactionPerks(incident_response_pct=0.15),
    FactionOption.RAIDERS: FactionPerks(melee_damage_pct=0.10),
    FactionOption.SUPER_MUTANT_TRIBE: FactionPerks(melee_damage_pct=0.15),
    FactionOption.CHILDREN_OF_ATOM: FactionPerks(radiation_resist_pct=0.5),
    FactionOption.THE_INSTITUTE: FactionPerks(production_pct=0.10),
    FactionOption.CAESARS_LEGION: FactionPerks(melee_damage_pct=0.15),
    FactionOption.RAILROAD: FactionPerks(),
    FactionOption.NCR: FactionPerks(),
    FactionOption.NONE: FactionPerks(),
}


def faction_of(entity: object) -> FactionOption | None:
    """Read an entity's faction from its ``visual_attributes`` JSONB, if present and valid."""
    attrs = getattr(entity, "visual_attributes", None)
    raw = attrs.get("faction") if isinstance(attrs, dict) else None
    if raw is None:
        return None
    try:
        return FactionOption(raw)
    except ValueError:
        return None


def perks_for_faction(entity: object) -> FactionPerks:
    """Faction perks for an entity; unknown or missing factions are neutral."""
    return FACTION_PERKS.get(faction_of(entity), FACTION_PERKS[FactionOption.NONE])
