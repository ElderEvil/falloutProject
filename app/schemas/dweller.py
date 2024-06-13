from datetime import datetime
from typing import Any

from pydantic import UUID4, ConfigDict, Field, model_validator
from sqlmodel import SQLModel

from app.models.base import SPECIALModel
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

    @classmethod
    @model_validator(mode="before")
    def validate_stats(cls, values: dict[str, Any]):
        health = values.get("health")
        max_health = values.get("max_health")
        rarity = values["rarity"]
        stat_min, stat_max = STATS_RANGE_BY_RARITY[rarity]

        if health > max_health:
            error_msg = f"Invalid health value: {health}. It cannot be greater than max_health."
            raise ValueError(error_msg)

        for stat_field in SPECIALModel.__annotations__:
            stat_value = values[stat_field]
            if not stat_min <= stat_value <= stat_max:
                error_msg = (
                    f"Invalid {rarity} dweller stat value: {stat_value}. "
                    f"It should be between {stat_min} and {stat_max}"
                )
                raise ValueError(error_msg)
        return values

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


class DwellerReadFull(DwellerRead):
    vault: VaultRead
    room: RoomRead | None
    weapon: WeaponRead | None
    outfit: OutfitRead | None


@optional()
class DwellerUpdate(DwellerBase):
    room_id: UUID4 | None = None
