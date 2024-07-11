from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import RoomTypeEnum, SPECIALEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.vault import Vault


class RoomBase(SQLModel):
    name: str = Field(index=True, min_length=3, max_length=32)
    category: RoomTypeEnum
    ability: SPECIALEnum | None
    population_required: int | None = Field(ge=12, le=100, default=None)
    base_cost: int = Field(ge=100, le=10_000)
    incremental_cost: int | None = Field(default=None, le=7_500)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1_500, le=150_000)
    capacity: int | None = None
    output: str | None = Field(default=None)
    size_min: int = Field(ge=1, le=9)
    size_max: int = Field(ge=1, le=9)
    size: int | None = Field(default=None, ge=1, le=9)
    tier: int = Field(default=1, ge=1, le=3)
    coordinate_x: int | None = Field(default=None, ge=0, le=8)
    coordinate_y: int | None = Field(default=None, ge=0, le=25)

    @property
    def is_unique(self) -> bool:
        return not self.incremental_cost

    @property
    def max_tier(self) -> int:
        """Determine the maximum tier of the room based on available upgrade costs."""
        if self.t2_upgrade_cost is not None and self.t3_upgrade_cost is not None:
            return 3
        if self.t2_upgrade_cost is not None:
            return 2
        return 1


class Room(BaseUUIDModel, RoomBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="rooms")

    dwellers: list["Dweller"] = Relationship(back_populates="room")

    def __str__(self):
        return f"{self.name}"
