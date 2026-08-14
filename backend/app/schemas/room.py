from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.room import RoomBase
from app.utils.partial import optional


class RoomCreateWithoutVaultID(RoomBase):
    capacity_formula: str | None = None
    output_formula: str | None = None


class RoomCreate(RoomCreateWithoutVaultID):
    vault_id: UUID4


class RoomBuild(SQLModel):
    """The only player-controlled input for building a room."""

    model_config = {"extra": "forbid"}

    vault_id: UUID4
    room_name: str = Field(min_length=3, max_length=32)
    coordinate_x: int = Field(ge=0, le=7)
    coordinate_y: int = Field(ge=0, le=15)


class RoomRead(RoomBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class RoomUpdate(RoomBase):
    pass
