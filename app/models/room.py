from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, SQLModel, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import RoomType, SPECIAL

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.vault import Vault


class RoomBase(SQLModel):
    name: str = Field(index=True, min_length=3, max_length=32)
    category: RoomType
    ability: SPECIAL | None
    population_required: int | None = Field(ge=12, le=100, default=None)
    base_cost: int = Field(ge=100, le=10_000)
    incremental_cost: int = Field(ge=25, le=5_000)
    t2_upgrade_cost: int | None = Field(ge=500, le=50_000)
    t3_upgrade_cost: int | None = Field(ge=1500, le=150_000)
    output: str | None = Field(default=None)
    size_min: int = Field(ge=1, le=6)
    size_max: int = Field(ge=1, le=9)

    tier: int = Field(ge=1, le=3, default=1)
    max_tier: int = Field(ge=1, le=3, default=1)


class Room(BaseUUIDModel, RoomBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="rooms")

    dwellers: list["Dweller"] = Relationship(back_populates="room")

    def __str__(self):
        return f"{self.name}({self.tier}/{self.max_tier})"
