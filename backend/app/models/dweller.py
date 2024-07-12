from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, SPECIALModel, TimeStampMixin
from app.schemas.common import GenderEnum, RarityEnum

if TYPE_CHECKING:
    from app.models.outfit import Outfit
    from app.models.room import Room
    from app.models.vault import Vault
    from app.models.weapon import Weapon


class DwellerBaseWithoutStats(SQLModel):
    # General info
    first_name: str = Field(index=True, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, index=True, max_length=32)
    is_adult: bool = True
    gender: GenderEnum = Field()
    rarity: RarityEnum = Field()

    # Backstory and appearance
    bio: str | None = Field(default=None, max_length=1024)
    visual_attributes: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
    image_url: str | None = Field(default=None, max_length=255)
    thumbnail_url: str | None = Field(default=None, max_length=255)

    # Stats
    level: int = Field(default=1, ge=1, le=50)
    experience: int = Field(default=0, ge=0)
    max_health: int = Field(default=50, ge=50, le=1_000)
    health: int = Field(default=50, ge=0, le=1_000)
    radiation: int = Field(default=0, ge=0, le=1_000)
    happiness: int = Field(default=50, ge=10, le=100)

    # Inventory
    stimpack: int = Field(default=0, ge=0, le=15)
    radaway: int = Field(default=0, ge=0, le=15)

    # TBD
    # status: str
    # job: str | None


class DwellerBase(DwellerBaseWithoutStats, SPECIALModel):
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="dwellers")

    room_id: UUID4 = Field(default=None, foreign_key="room.id", nullable=True)
    room: "Room" = Relationship(back_populates="dwellers")

    # Inventory
    weapon: "Weapon" = Relationship(back_populates="dweller", sa_relationship_kwargs={"cascade": "all, delete"})
    outfit: "Outfit" = Relationship(back_populates="dweller", sa_relationship_kwargs={"cascade": "all, delete"})
