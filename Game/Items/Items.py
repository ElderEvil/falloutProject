from pydantic import root_validator
from sqlmodel import SQLModel, Field

from utilities.generic import Rarity


class Item(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    rarity: Rarity
    value: int | None

    value_by_rarity = {
        Rarity.common: 10,
        Rarity.rare: 100,
        Rarity.legendary: 500,
    }

    @root_validator
    def set_default_value(cls, values) -> int:
        if "value" not in values:
            values["value"] = cls.value_by_rarity[values["rarity"]]
        return values
