"""Room Rush quote and result contracts."""

from typing import Literal

from pydantic import UUID4, BaseModel

RushBlockedReason = Literal["not_production", "no_workers", "active_incident", "no_power", "room_busy"]


class RoomRushResourceGain(BaseModel):
    """Integer resource amounts actually applied (or previewed) by a rush."""

    power: int = 0
    food: int = 0
    water: int = 0
    stimpack: int = 0
    radaway: int = 0


class RoomRushQuote(BaseModel):
    """Server-computed rush risk and payout preview for one room.

    Chances are percentages in ``0..100``; the service keeps internal
    probabilities in ``0..1``.
    """

    can_rush: bool
    blocked_reason: RushBlockedReason | None
    fail_chance: float
    success_chance: float
    stacks: int
    max_stacks: int
    avg_ability: float
    avg_luck: float
    worker_count: int
    payout: RoomRushResourceGain
    caps_chance: float
    eligible_incidents: list[str]
    next_stack_penalty: float


class RoomRushResult(BaseModel):
    """Outcome of one rush attempt."""

    outcome: Literal["success", "failure"]
    payout: RoomRushResourceGain
    caps: int
    xp_per_worker: int
    happiness_delta: int
    incident_id: UUID4 | None
    incident_type: str | None
    stacks_after: int
    next_fail_chance: float
    message: str
