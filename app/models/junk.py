from enum import Enum

from sqlmodel import Field

from app.models.item import ItemBase, ItemUpdate
from utils.common import Rarity


class JunkType(str, Enum):
    CIRCUITRY = "Circuitry"
    LEATHER = "Leather"
    ADHESIVE = "Adhesive"
    CLOTH = "Cloth"
    SCIENCE = "Science"
    STEEL = "Steel"
    VALUABLES = "Valuables"


class JunkBase(ItemBase):
    junk_type: JunkType
    description: str

    _value_by_rarity = {
        Rarity.common: 2,
        Rarity.rare: 50,
        Rarity.legendary: 200,
    }

    def __str__(self):
        return f"{self.name} (Type: {self.junk_type.name}, Rarity: {self.rarity.name}, Value: {self.value})\n" \
               f"{self.description}"


class Junk(JunkBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class JunkCreate(JunkBase):
    pass


class JunkRead(JunkBase):
    id: int


class JunkUpdate(ItemUpdate):
    junk_type: str | None = None
    description: str | None = None
