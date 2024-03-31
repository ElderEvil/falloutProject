from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.dweller import Dweller
    from app.models.room import Room


class VaultBase(SQLModel):
    name: int = Field(index=True, gt=0, lt=1_000)
    bottle_caps: int = Field(default=1_000, ge=0, lt=1_000_000)
    happiness: int = Field(default=50, ge=0, le=100)

    power: int = Field(0, ge=0, le=10_000)
    power_max: int = Field(100, ge=100, le=10_000)
    food: int = Field(0, ge=0, le=10_000)
    food_max: int = Field(100, ge=100, le=10_000)
    water: int = Field(0, ge=0, le=10_000)
    water_max: int = Field(100, ge=100, le=10_000)

    def __str__(self):
        return f"Vault {self.name:03}"


class Vault(BaseUUIDModel, VaultBase, TimeStampMixin, table=True):
    user_id: UUID4 = Field(default=None, foreign_key="user.id")
    user: "User" = Relationship(back_populates="vaults")

    dwellers: list["Dweller"] = Relationship(back_populates="vault")
    rooms: list["Room"] = Relationship(back_populates="vault")
