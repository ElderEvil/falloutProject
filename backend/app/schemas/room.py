from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.core.grid_config import GRID_BUILD_X_MAX, GRID_BUILD_Y_MAX, GRID_X_MIN, GRID_Y_MIN
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
    coordinate_x: int = Field(ge=GRID_X_MIN, le=GRID_BUILD_X_MAX)
    coordinate_y: int = Field(ge=GRID_Y_MIN, le=GRID_BUILD_Y_MAX)


class RoomRead(RoomBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class RoomUpdate(RoomBase):
    pass
