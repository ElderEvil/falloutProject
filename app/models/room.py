from sqlmodel import Field, SQLModel

from app.schemas.common_schema import RoomType


class RoomBase(SQLModel):
    name: str = Field(..., index=True, min_length=3, max_length=32)
    category: RoomType = RoomType.misc
    ability: str
    population_required: int | None
    base_cost: int
    incremental_cost: int
    tier: int = 1
    max_tier: int = Field(ge=1, le=3, default=1)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1500, le=150_000)
    output: int | None
    size: int = Field(ge=1, le=9)


class Room(RoomBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
