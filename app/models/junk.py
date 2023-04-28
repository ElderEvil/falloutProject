from sqlmodel import Field

from app.models.item import ItemBase
from app.schemas.common_schema import Rarity, JunkType


class JunkBase(ItemBase):
    junk_type: JunkType
    description: str

    _value_by_rarity = {
        Rarity.common: 2,
        Rarity.rare: 50,
        Rarity.legendary: 200,
    }

    def __str__(self):
        return (
            f"{self.name} (Type: {self.junk_type.name}, Rarity: {self.rarity.name}, Value: {self.value})\n"
            f"{self.description}"
        )


class Junk(JunkBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
