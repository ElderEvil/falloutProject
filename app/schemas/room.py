from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.room import RoomBase
from app.schemas.common import RoomType


class RoomCreate(RoomBase):
    vault_id: UUID4


class RoomRead(RoomBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class RoomUpdate(SQLModel):
    name: str | None = Field(index=True, min_length=3, max_length=32)
    category: RoomType | None
    ability: str | None = None
    population_required: int | None = Field(ge=12, le=100, default=None)
    base_cost: int | None = Field(ge=100, le=10_000, default=None)
    incremental_cost: int | None = Field(ge=25, le=5_000, default=None)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1_500, le=150_000)
    output: int | None
    size_min: int | None = Field(ge=1, le=3)
    size_max: int | None = Field(ge=1, le=9)

    tier: int | None = Field(ge=1, le=3, default=None)
    max_tier: int | None = Field(ge=1, le=3)
