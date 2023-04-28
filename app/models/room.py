from enum import Enum

from sqlmodel import SQLModel, Field


class RoomType(str, Enum):
    CAPACITY = "Capacity"
    CRAFTING = "Crafting"
    MISC = "Misc"
    PRODUCTION = "Production"
    QUESTS = "Quests"
    THEME = "Theme"
    TRAINING = "Training"


class RoomBase(SQLModel):
    name: str = Field(..., index=True, min_length=3, max_length=32)
    category: RoomType = RoomType.MISC
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


class RoomCreate(RoomBase):
    pass


class RoomRead(RoomBase):
    id: int


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
