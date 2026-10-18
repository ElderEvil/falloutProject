"""Typed catalog records for procedural dweller generation."""

from collections.abc import Sequence
from typing import NotRequired, TypedDict

from app.core.enums import FactionEnum, RaceEnum


class AppearancePools(TypedDict, total=False):
    """Optional trait subsets; omitted fields use the canonical appearance options."""

    skin_tone: Sequence[str]
    hair_color: Sequence[str]
    hair_style: Sequence[str]
    build: Sequence[str]
    expression: Sequence[str]


class DwellerArchetype(TypedDict):
    """Generation data plus optional authored visual defaults for legacy consumers."""

    race: RaceEnum
    faction: FactionEnum
    weight: int
    appearance_pools: AppearancePools
    personality_lines: Sequence[str]
    skin_tone: NotRequired[str]
    build: NotRequired[str]
    hair_style: NotRequired[str]
    headgear: NotRequired[str]
    outfit: NotRequired[str]
    weapon: NotRequired[str]
    pose: NotRequired[str]
    background: NotRequired[str]
