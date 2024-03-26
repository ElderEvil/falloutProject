from pydantic import UUID4
from sqlmodel import Field, SQLModel, Relationship
from typing import TYPE_CHECKING

from app.models.base import SPECIAL, BaseUUIDModel, TimeStampMixin
from app.schemas.common import Gender, Rarity

if TYPE_CHECKING:
    from app.models.vault import Vault
    from app.models.room import Room


class DwellerBaseWithoutStats(SQLModel):
    first_name: str = Field(index=True, min_length=3, max_length=32)
    last_name: str = Field(index=True, min_length=3, max_length=32)
    gender: Gender = Field()
    rarity: Rarity = Field()
    level: int = Field(ge=1, le=50, default=1)
    experience: int = Field(ge=0, default=0)
    max_health: int = Field(ge=50, le=1000, default=50)
    health: int = Field(ge=0, le=1000, default=50)
    happiness: int = Field(ge=10, le=100, default=50)
    is_adult: bool = True


class DwellerBase(DwellerBaseWithoutStats, SPECIAL):
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class DwellerBlueprint(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True): ...


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="dwellers")

    room_id: UUID4 = Field(default=None, foreign_key="room.id", nullable=True)
    room: "Room" = Relationship(back_populates="dwellers")

    weapon_id: UUID4 = Field(default=None, foreign_key="weapon.id", nullable=True)
    outfit_id: UUID4 = Field(default=None, foreign_key="outfit.id", nullable=True)
