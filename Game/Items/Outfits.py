import random

from Game.Items.Items import Item, ItemRarity


class Outfit(Item):
    def __init__(self, name: str, rarity: ItemRarity, sex: str = None):
        super().__init__(name, rarity)
        self.type = "Outfit"
        self.sex = sex
        self.stats = {}
        self.gender = None
        stat_total = self.rarity.value['stat_total']
        for special_stat in random.choices(['S', 'P', 'E', 'C', 'I', 'A', 'L'], k=stat_total):
            if special_stat in self.stats:
                self.stats[special_stat] += 1
            else:
                self.stats[special_stat] = 1

    def __str__(self):
        return f"{self.name} (Type: {self.type}, Rarity: {self.rarity.value['name']}," \
               f" Stats: {self.stats}, Value: {self.value})"


class TieredOutfit(Outfit):
    def __init__(self, rarity: ItemRarity, name: str = None):
        super().__init__(name, rarity)
        self.type = 'Tiered Outfit'
        self.prefix = self._get_prefix_by_rarity()
        self.armor_name_list = [
            " vault suit",
            " battle armor",
            " leather armor",
            " wasteland gear",
            " BoS uniform",
            " metal armor",
        ]
        self.name = self.prefix + random.choice(self.armor_name_list)

    def _get_prefix_by_rarity(self):
        prefixes = {
            "Common": "Armored",
            "Rare": "Sturdy",
            "Legendary": "Heavy",
        }
        return prefixes[self.rarity.value['name']]


class CommonOutfit(Outfit):
    def __init__(self, name: str = None):
        super().__init__(name, ItemRarity.COMMON)
        self.type = "Common Outfit"


class RareOutfit(Outfit):
    def __init__(self, name: str = None):
        super().__init__(name, ItemRarity.RARE)
        self.type = "Rare Outfit"


class LegendaryOutfit(Outfit):
    def __init__(self, name: str = None):
        super().__init__(name, ItemRarity.LEGENDARY)
        self.type = "Legendary Outfit"


class PowerArmor(Outfit):
    def __init__(self, name: str = None):
        super().__init__(name, ItemRarity.LEGENDARY)
        self.type = "Power Armor"
        self.suffixes = {"a", "d", "f", "MK I", "MK IV", "MK VI", }
        self.subtypes = {"T-45", "T-51", "T-60", "X-01", }
