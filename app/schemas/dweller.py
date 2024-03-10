from datetime import datetime
from typing import Any

from pydantic import UUID4, Field, model_validator
from sqlmodel import SQLModel

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
    @classmethod
    @model_validator(mode="before")
    @classmethod
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


class DwellerRead(DwellerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class DwellerUpdate(SQLModel):
    first_name: str | None = Field(min_length=3, max_length=32)
    last_name: str | None = Field(min_length=3, max_length=32)
    gender: Gender | None = None
    rarity: Rarity | None = None
    level: int | None = Field(ge=1, le=50, default=1)
    experience: int | None = Field(ge=0, default=0)
    max_health: int | None = Field(ge=50, le=1000, default=50)
    health: int | None = Field(ge=0, le=1000, default=50)
    happiness: int | None = Field(ge=10, le=100, default=50)
    is_adult: bool | None = True
