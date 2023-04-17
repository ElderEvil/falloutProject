from enum import Enum

from sqlmodel import SQLModel, Field

from utilities.generic import Rarity, Gender


class OutfitType(str, Enum):
    CommonOutfit = "Common Outfit"
    RareOutfit = "Rare Outfit"
    LegendaryOutfit = "Legendary Outfit"
    PowerArmor = "Power Armor"
    TieredOutfit = "Tiered Outfit"


class Outfit(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    rarity: Rarity
    value: int
    gender: Gender | None = None
    stats: dict = Field(default={})
    type: OutfitType = "Common Outfit"

    def get_value_by_rarity(self):
        rarity_value = {
            "common": 10,
            "rare": 100,
            "legendary": 500,
        }
        return rarity_value[self.rarity]

    def __str__(self):
        return f"🛡️{self.name}"