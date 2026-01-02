"""Pydantic schemas for radio recruitment system."""

from pydantic import Field
from sqlmodel import SQLModel

from app.schemas.dweller import DwellerCreateCommonOverride, DwellerRead


class SpeedupMultiplier(SQLModel):
    """Speedup multiplier for a radio room."""

    room_id: str
    speedup: float


class RadioStatsRead(SQLModel):
    """Radio recruitment statistics."""

    has_radio: bool
    recruitment_rate: float  # Per minute
    rate_per_hour: float
    estimated_hours_per_recruit: float
    radio_rooms_count: int
    manual_cost_caps: int
    radio_mode: str
    speedup_multipliers: list[SpeedupMultiplier]


class ManualRecruitRequest(SQLModel):
    """Request to manually recruit a dweller for caps."""

    override: DwellerCreateCommonOverride | None = Field(
        default=None, description="Optional overrides for the recruited dweller attributes"
    )


class RecruitmentResponse(SQLModel):
    """Response after recruiting a dweller."""

    dweller: DwellerRead
    message: str
    caps_spent: int | None = Field(default=None, description="Caps spent if manual recruitment")
