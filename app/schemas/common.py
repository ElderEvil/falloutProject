from enum import StrEnum


class RarityEnum(StrEnum):
    COMMON = "common"
    RARE = "rare"
    LEGENDARY = "legendary"


class SPECIALEnum(StrEnum):
    STRENGTH = "strength"
    PERCEPTION = "perception"
    ENDURANCE = "endurance"
    CHARISMA = "charisma"
    INTELLIGENCE = "intelligence"
    AGILITY = "agility"
    LUCK = "luck"


class GenderEnum(StrEnum):
    MALE = "male"
    FEMALE = "female"


class JunkTypeEnum(StrEnum):
    CIRCUITRY = "circuitry"
    LEATHER = "leather"
    ADHESIVE = "adhesive"
    CLOTH = "cloth"
    SCIENCE = "science"
    STEEL = "steel"
    VALUABLES = "valuables"


class OutfitTypeEnum(StrEnum):
    COMMON = "common_outfit"
    RARE = "rare_outfit"
    LEGENDARY = "legendary_outfit"
    POWER_ARMOR = "power_armor"
    TIERED = "tiered_outfit"


class RoomActionEnum(StrEnum):
    BUILD = "build"
    UPGRADE = "upgrade"
    DESTROY = "destroy"


class RoomTypeEnum(StrEnum):
    CAPACITY = "capacity"
    CRAFTING = "crafting"
    MISC = "misc."
    PRODUCTION = "production"
    QUESTS = "quests"
    THEME = "theme"
    TRAINING = "training"


class WeaponTypeEnum(StrEnum):
    MELEE = "melee"
    GUN = "gun"
    ENERGY = "energy"
    HEAVY = "heavy"


class WeaponSubtypeEnum(StrEnum):
    BLUNT = "blunt"
    EDGED = "edged"
    POINTED = "pointed"
    PISTOL = "pistol"
    RIFLE = "rifle"
    SHOTGUN = "shotgun"
    AUTOMATIC = "automatic"
    EXPLOSIVE = "explosive"
    FLAMER = "flamer"
