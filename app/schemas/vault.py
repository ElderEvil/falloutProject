from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.vault import VaultBase


class VaultCreate(VaultBase):
    name: int = Field(gt=0, lt=1_000)


class VaultCreateWithUserID(VaultBase):
    user_id: UUID4


class VaultStart(SQLModel):
    name: int = Field(gt=0, lt=1_000)


class VaultRead(VaultBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class VaultReadWithUser(VaultRead):
    user_id: UUID4


class VaultUpdate(SQLModel):
    name: int | None = Field(default=None, gt=0, lt=1_000)
    bottle_caps: int | None = Field(default=None, ge=0, lt=1_000_000)
    happiness: int | None = Field(default=50, ge=0, le=100)

    power: int | None = Field(default=None, ge=0, le=10_000)
    power_max: int | None = Field(default=None, gt=100, le=10_000)
    food: int | None = Field(default=None, ge=0, le=10_000)
    food_max: int | None = Field(default=None, gt=100, le=10_000)
    water: int | None = Field(default=None, ge=0, le=10_000)
    water_max: int | None = Field(default=None, gt=100, le=10_000)
