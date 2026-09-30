from datetime import datetime
from typing import Literal

from pydantic import UUID4, computed_field
from sqlmodel import Field, SQLModel
from sqlmodel.main import SQLModelConfig

from app.core.grid_config import GRID_BUILD_X_MAX, GRID_BUILD_Y_MAX, GRID_X_MIN, GRID_Y_MIN
from app.models.room import RoomBase
from app.utils.partial import optional
from app.utils.room_assets import get_room_detail_scene


class RoomDetailActorSlot(SQLModel):
    id: str
    x: int
    y: int
    facing: Literal["left", "right"]
    scale: float = 1.0


class RoomDetailScene(SQLModel):
    image_url: str
    width: int
    height: int
    camera: str
    safe_crop: tuple[int, int, int, int]
    floor_baseline_y: int
    actor_slots: list[RoomDetailActorSlot]


class RoomCreateWithoutVaultID(RoomBase):
    capacity_formula: str | None = None
    output_formula: str | None = None


class RoomCreate(RoomCreateWithoutVaultID):
    vault_id: UUID4


class RoomBuild(SQLModel):
    """The only player-controlled input for building a room."""

    model_config = SQLModelConfig(extra="forbid")

    vault_id: UUID4
    room_name: str = Field(min_length=3, max_length=32)
    coordinate_x: int = Field(ge=GRID_X_MIN, le=GRID_BUILD_X_MAX)
    coordinate_y: int = Field(ge=GRID_Y_MIN, le=GRID_BUILD_Y_MAX)


class RoomRead(RoomBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def detail_scene(self) -> RoomDetailScene | None:
        """Detail-modal scene art and actor anchors from the asset manifest, if registered."""
        return get_room_detail_scene(self.name, tier=self.tier, size=self.size or self.size_min)


@optional()
class RoomUpdate(RoomBase):
    pass
