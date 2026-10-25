"""Resolved combat facts shared by Arena and incident presentation."""

from typing import Literal

from pydantic import BaseModel, Field

CombatEffect = Literal[
    "strike", "punch", "thrust", "shot", "beam", "pulse", "burst", "sweep", "flame", "blast", "debris"
]
CombatBody = Literal["human", "ghoul", "feral", "mutant", "behemoth", "synth", "power-armor"]
CombatSkillIcon = Literal[
    "unarmed",
    "melee-blunt",
    "melee-edged",
    "melee-pointed",
    "gun-pistol",
    "gun-rifle",
    "gun-shotgun",
    "energy-pistol",
    "energy-rifle",
    "heavy-automatic",
    "heavy-flamer",
    "heavy-explosive",
]


class CombatImpact(BaseModel):
    target_id: str
    body: CombatBody = "human"
    damage: int = Field(ge=0)
    # A grouped incident threat has no individual HP; do not invent it.
    health_before: int | None = None
    health_after: int | None = None


class CombatAction(BaseModel):
    actor_id: str
    actor_body: CombatBody = "human"
    effect: CombatEffect = "strike"
    skill: str | None = None
    skill_icon: CombatSkillIcon | None = None
    targets: list[CombatImpact]
