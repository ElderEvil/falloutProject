from enum import Enum

from sqlmodel import Field

from app.models.item import ItemBase, ItemUpdate
from utils.common import Gender


class OutfitType(str, Enum):
    CommonOutfit = "Common Outfit"
    RareOutfit = "Rare Outfit"
    LegendaryOutfit = "Legendary Outfit"
    PowerArmor = "Power Armor"
    TieredOutfit = "Tiered Outfit"


class OutfitBase(ItemBase):
    outfit_type: OutfitType = OutfitType.CommonOutfit
    gender: Gender | None = None


class Outfit(OutfitBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class OutfitCreate(OutfitBase):
    pass


class OutfitRead(OutfitBase):
    id: int


class OutfitUpdate(ItemUpdate):
    outfit_type: OutfitType | None = None
    gender: Gender | None = None
