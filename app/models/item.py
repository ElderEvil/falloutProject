from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.schemas.common import Rarity


class ItemBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=3, max_length=32)
    rarity: Rarity
    value: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=255)

    _value_by_rarity = {
        Rarity.common: 10,
        Rarity.rare: 100,
        Rarity.legendary: 500,
    }

    @classmethod
    @field_validator("value", mode="before")
    def set_default_value(cls, values) -> int:
        if "value" not in values:
            values["value"] = cls._value_by_rarity[values["rarity"]]
        return values
