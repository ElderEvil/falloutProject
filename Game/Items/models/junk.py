from sqlmodel import Field

from Game.Items.models.items import ItemBase, ItemUpdate
from utilities.common import Rarity


class JunkBase(ItemBase):
    junk_type: str
    description: str

    _value_by_rarity = {
        Rarity.common: 2,
        Rarity.rare: 50,
        Rarity.legendary: 200,
    }

    def __str__(self):
        return f"{self.name} (Type: {self.junk_type}, Rarity: {self.rarity.name})"


class Junk(JunkBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class JunkCreate(JunkBase):
    pass


class JunkRead(JunkBase):
    id: int


class JunkUpdate(ItemUpdate):
    junk_type: str | None = None
    description: str | None = None
