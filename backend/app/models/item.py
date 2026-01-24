from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.schemas.common import RarityEnum


class ItemBase(SQLModel):
    name: str = Field(index=True, min_length=3, max_length=32)
    rarity: RarityEnum
    value: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=255)

    _value_by_rarity = {
        RarityEnum.COMMON: 10,
        RarityEnum.RARE: 100,
        RarityEnum.LEGENDARY: 500,
    }

    @classmethod
    @field_validator("value", mode="before")
    def set_default_value(cls, values) -> int:
        if "value" not in values:
            values["value"] = cls._value_by_rarity[values["rarity"]]
        return values
