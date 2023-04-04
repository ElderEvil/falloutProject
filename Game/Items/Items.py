from dataclasses import dataclass
from enum import Enum


class ItemRarity(Enum):
    COMMON = {'name': 'Common', 'stat_total': 3, 'value': 10}
    RARE = {'name': 'Rare', 'stat_total': 5, 'value': 100}
    LEGENDARY = {'name': 'Legendary', 'stat_total': 7, 'value': 500}


class Item:
    def __init__(self, name: str, rarity: ItemRarity):
        self.name = name
        self.rarity = rarity
        self.value = rarity.value['value']


@dataclass(frozen=True)
class Stimpak(Item):
    name = "Stimpak"
    rarity = ItemRarity.COMMON


@dataclass(frozen=True)
class RadAway(Item):
    name = "RadAway"
    rarity = ItemRarity.COMMON
