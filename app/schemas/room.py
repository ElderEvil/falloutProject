from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.room import RoomBase
from app.schemas.common import RoomType


class RoomCreate(RoomBase):
    pass


class RoomRead(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime


class RoomUpdate(SQLModel):
    name: str | None = Field(index=True, min_length=3, max_length=32)
    category: RoomType | None
    ability: str | None
    population_required: int | None
    base_cost: int | None
    incremental_cost: int | None
    tier: int | None
    max_tier: int | None = Field(ge=1, le=3)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1500, le=150_000)
    output: int | None
    size: int | None = Field(ge=1, le=9)
