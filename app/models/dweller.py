from pydantic import UUID4
from sqlmodel import Field, SQLModel, Relationship
from typing import TYPE_CHECKING

from app.models.base import SPECIALModel, BaseUUIDModel, TimeStampMixin

from app.schemas.common import Gender, Rarity

if TYPE_CHECKING:
    from app.models.vault import Vault
    from app.models.room import Room
    from app.models.weapon import Weapon
    from app.models.outfit import Outfit


class DwellerBaseWithoutStats(SQLModel):
    # General info
    first_name: str = Field(index=True, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, index=True, max_length=32)
    is_adult: bool = True
    gender: Gender = Field()
    rarity: Rarity = Field()

    # Stats
    level: int = Field(ge=1, le=50, default=1)
    experience: int = Field(ge=0, default=0)
    max_health: int = Field(ge=50, le=1_000, default=50)
    health: int = Field(ge=0, le=1_000, default=50)
    radiation: int = Field(ge=0, le=1_000, default=0)
    happiness: int = Field(ge=10, le=100, default=50)

    # Inventory
    stimpack: int = Field(default=0, ge=0, le=15)
    radaway: int = Field(default=0, ge=0, le=15)


class DwellerBase(DwellerBaseWithoutStats, SPECIALModel):
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="dwellers")

    room_id: UUID4 = Field(default=None, foreign_key="room.id", nullable=True)
    room: "Room" = Relationship(back_populates="dwellers")

    # Inventory
    weapon: "Weapon" = Relationship(back_populates="dweller")
    outfit: "Outfit" = Relationship(back_populates="dweller")
