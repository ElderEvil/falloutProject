"""Contracts for the single-rank Fallout-inspired explorer perk pilot."""

from typing import Literal

from pydantic import UUID4, BaseModel

from app.core.enums import DwellerPerk


class PerkDefinition(BaseModel):
    id: DwellerPerk
    name: str
    description: str
    stat: Literal["intelligence", "charisma"]
    minimum_stat: int
    minimum_level: int = 5


class PerkOption(PerkDefinition):
    eligible: bool
    unavailable_reason: str | None = None


class DwellerPerksRead(BaseModel):
    dweller_id: UUID4
    selected_perk: DwellerPerk | None
    options: list[PerkOption]


class PerkSelectRequest(BaseModel):
    perk: DwellerPerk
