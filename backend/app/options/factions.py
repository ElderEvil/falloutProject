"""Faction options with race-based restrictions."""

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
