"""Small authored perk catalog. Effects belong to authored encounter options."""

from app.core.enums import DwellerPerk
from app.schemas.perk import PerkDefinition

PERKS = {
    DwellerPerk.HACKER: PerkDefinition(
        id=DwellerPerk.HACKER,
        name="Hacker",
        description="Access terminal solutions at wasteland encounters. Override the Research Checkpoint's security console.",
        stat="intelligence",
        minimum_stat=4,
    ),
    DwellerPerk.TERRIFYING_PRESENCE: PerkDefinition(
        id=DwellerPerk.TERRIFYING_PRESENCE,
        name="Terrifying Presence",
        description="Unlock intimidation dialogue. Demand spare equipment from the Research Checkpoint's scavengers.",
        stat="charisma",
        minimum_stat=6,
    ),
}
