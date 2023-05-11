from enum import Enum


class Rarity(str, Enum):
    common = "Common"
    rare = "Rare"
    legendary = "Legendary"


class Gender(str, Enum):
    male = "Male"
    female = "Female"


class JunkType(str, Enum):
    circuitry = "Circuitry"
    leather = "Leather"
    adhesive = "Adhesive"
    cloth = "Cloth"
    science = "Science"
    steel = "Steel"
    valuables = "Valuables"


class OutfitType(str, Enum):
    common = "Common Outfit"
    rare = "Rare Outfit"
    legendary = "Legendary Outfit"
    power_armor = "Power Armor"
    tiered = "Tiered Outfit"


class RoomType(str, Enum):
    capacity = "Capacity"
    crafting = "Crafting"
    misc = "Misc"
    production = "Production"
    quests = "Quests"
    theme = "Theme"
    training = "Training"


class WeaponType(str, Enum):
    melee = "Melee"
    gun = "Gun"
    energy = "Energy"
    heavy = "Heavy"


class WeaponSubtype(str, Enum):
    blunt = "Blunt"
    edged = "Edged"
    pointed = "Pointed"
    pistol = "Pistol"
    rifle = "Rifle"
    shotgun = "Shotgun"
    automatic = "Automatic"
    explosive = "Explosive"
    flamer = "Flamer"
