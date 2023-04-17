from enum import Enum

from sqlmodel import Field

from Game.Items.models.items import ItemBase, ItemUpdate
from utils.common import Rarity


class JunkType(str, Enum):
    Circuitry = "Circuitry"
    Leather = "Leather"
    Adhesive = "Adhesive"
    Cloth = "Cloth"
    Science = "Science"
    Steel = "Steel"
    Valuables = "Valuables"


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
