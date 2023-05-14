from pydantic import validator
from sqlmodel import Field, SQLModel

from app.schemas.common import Rarity


class ItemBase(SQLModel):
    name: str = Field(unique=True, index=True, min_length=3, max_length=32)
    rarity: Rarity
    value: int | None = Field(default=None, ge=0)

    _value_by_rarity = {
        Rarity.common: 10,
        Rarity.rare: 100,
        Rarity.legendary: 500,
    }

    @classmethod
    @validator("value", pre=True)
    def set_default_value(cls, values) -> int:  # noqa: ANN001
        if "value" not in values:
            values["value"] = cls._value_by_rarity[values["rarity"]]
        return values
