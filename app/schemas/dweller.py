from datetime import datetime
from typing import Any

from pydantic import UUID4, Field, model_validator
from sqlalchemy import Column
from sqlmodel import SQLModel, Enum

from app.models.base import SPECIAL
from app.models.dweller import DwellerBase
from app.schemas.common import Gender, Rarity

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


class DwellerCreate(DwellerBase):
    vault_id: UUID4

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

        for stat_field in SPECIAL.__fields__:
            stat_value = values[stat_field]
            if not stat_min <= stat_value <= stat_max:
                error_msg = (
                    f"Invalid {rarity} dweller stat value: {stat_value}. "
                    f"It should be between {stat_min} and {stat_max}"
                )
                raise ValueError(error_msg)
        return values


class DwellerCreateCommon(SQLModel):
    rarity: Rarity = Field(default=Rarity.common)
    gender: Gender | None = Field(default=None, sa_column=Column(Enum(Gender)))


class DwellerRead(DwellerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class DwellerUpdate(SQLModel):
    first_name: str | None = Field(min_length=3, max_length=32)
    last_name: str | None = Field(min_length=3, max_length=32)
    is_adult: bool | None = True
    gender: Gender | None = None
    rarity: Rarity | None = None
    level: int | None = Field(ge=1, le=50, default=1)
    experience: int | None = Field(ge=0, default=0)
    max_health: int | None = Field(ge=50, le=1_000, default=50)
    health: int | None = Field(ge=0, le=1_000, default=50)
    radiation: int | None = Field(ge=0, le=1_000, default=0)
    happiness: int | None = Field(ge=10, le=100, default=50)
    stimpack: int | None = Field(default=0, ge=0, le=15)
    radaway: int | None = Field(default=0, ge=0, le=15)
