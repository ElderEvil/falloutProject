from datetime import datetime

from pydantic import UUID4, ConfigDict, Field
from sqlmodel import SQLModel

from app.models.dweller import DwellerBase
from app.schemas.common import SPECIAL, Gender, Rarity
from app.schemas.outfit import OutfitRead
from app.schemas.room import RoomRead
from app.schemas.vault import VaultRead
from app.schemas.weapon import WeaponRead
from app.utils.partial import optional

LETTER_TO_STAT = {
    "S": "strength",
    "P": "perception",
    "E": "endurance",
    "C": "charisma",
    "A": "agility",
    "I": "intelligence",
    "L": "luck",
}

STATS_RANGE_BY_RARITY = {
    Rarity.common: (1, 3),
    Rarity.rare: (3, 6),
    Rarity.legendary: (6, 10),
}


class DwellerCreateWithoutVaultID(DwellerBase):
    weapon: str | None = Field(default=None, max_length=32)
    outfit: str | None = Field(default=None, max_length=32)

    model_config = ConfigDict(use_enum_values=True)


class DwellerCreate(DwellerCreateWithoutVaultID):
    vault_id: UUID4


class DwellerCreateCommonOverride(SQLModel):
    """Common random dweller overrides."""

    first_name: str | None = Field(default=None, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, min_length=2, max_length=32)
    rarity: Rarity = Field(default=Rarity.common)
    gender: Gender | None = Field(default=None)
    special_boost: SPECIAL | None = Field(default=None)


class DwellerRead(DwellerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class DwellerReadWithVaultID(DwellerRead):
    vault_id: UUID4


class DwellerReadWithRoomID(DwellerRead):
    room_id: UUID4

    model_config = ConfigDict(from_attributes=True)


class DwellerReadFull(DwellerRead):
    vault: VaultRead
    room: RoomRead | None
    weapon: WeaponRead | None
    outfit: OutfitRead | None

    model_config = ConfigDict(from_attributes=True)


@optional()
class DwellerUpdate(DwellerBase):
    room_id: UUID4 | None = None
