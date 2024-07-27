from datetime import datetime

from pydantic import UUID4, ConfigDict, Field
from sqlmodel import SQLModel

from app.models.dweller import DwellerBase
from app.schemas.common import GenderEnum, RarityEnum, SPECIALEnum
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
    RarityEnum.COMMON: (1, 3),
    RarityEnum.RARE: (3, 6),
    RarityEnum.LEGENDARY: (6, 10),
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
    gender: GenderEnum | None = Field(default=None)
    special_boost: SPECIALEnum | None = Field(default=None)


class DwellerReadLess(SQLModel):
    id: UUID4
    first_name: str
    last_name: str | None
    thumbnail_url: str | None
    level: int
    health: int
    max_health: int
    radiation: int
    happiness: int

    # TBD
    # status: str
    # job: str | None


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
