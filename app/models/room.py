from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import RoomType


class RoomBase(SQLModel):
    name: str = Field(..., index=True, min_length=3, max_length=32)
    category: RoomType = RoomType.misc
    ability: str
    population_required: int | None = Field(ge=12, le=100, default=None)
    base_cost: int = Field(..., ge=100, le=10_000)
    incremental_cost: int = Field(..., ge=25, le=5_000)
    tier: int = Field(ge=1, le=3, default=1)
    max_tier: int = Field(ge=1, le=3, default=1)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1500, le=150_000)
    output: int | None
    size: int = Field(ge=1, le=9)


class Room(BaseUUIDModel, RoomBase, TimeStampMixin, table=True):
    ...
