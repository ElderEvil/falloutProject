"""Resolved combat facts shared by Arena and incident presentation."""

from typing import Literal

from pydantic import BaseModel, Field

CombatEffect = Literal["strike", "shot", "beam", "sweep", "flame", "blast"]


class CombatImpact(BaseModel):
    target_id: str
    damage: int = Field(ge=0)
    # A grouped incident threat has no individual HP; do not invent it.
    health_before: int | None = None
    health_after: int | None = None


class CombatAction(BaseModel):
    actor_id: str
    effect: CombatEffect = "strike"
    skill: str | None = None
    targets: list[CombatImpact]
