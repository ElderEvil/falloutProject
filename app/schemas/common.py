from enum import StrEnum


class CaseInsensitiveEnum(StrEnum):
    @classmethod
    def _missing_(cls, value: str):
        for member in cls:
            if member.lower() == value.lower():
                return member
        return None


class RarityEnum(CaseInsensitiveEnum):
    COMMON = "common"
    RARE = "rare"
    LEGENDARY = "legendary"


class SPECIALEnum(CaseInsensitiveEnum):
    STRENGTH = "strength"
    PERCEPTION = "perception"
    ENDURANCE = "endurance"
    CHARISMA = "charisma"
    INTELLIGENCE = "intelligence"
    AGILITY = "agility"
    LUCK = "luck"


class GenderEnum(CaseInsensitiveEnum):
    MALE = "male"
    FEMALE = "female"


class JunkTypeEnum(CaseInsensitiveEnum):
    CIRCUITRY = "circuitry"
    LEATHER = "leather"
    ADHESIVE = "adhesive"
    CLOTH = "cloth"
    SCIENCE = "science"
    STEEL = "steel"
    VALUABLES = "valuables"


class OutfitTypeEnum(CaseInsensitiveEnum):
    COMMON = "common_outfit"
    RARE = "rare_outfit"
    LEGENDARY = "legendary_outfit"
    POWER_ARMOR = "power_armor"
    TIERED = "tiered_outfit"


class RoomActionEnum(CaseInsensitiveEnum):
    BUILD = "build"
    UPGRADE = "upgrade"
    DESTROY = "destroy"


class RoomTypeEnum(CaseInsensitiveEnum):
    CAPACITY = "capacity"
    CRAFTING = "crafting"
    MISC = "misc."
    PRODUCTION = "production"
    QUESTS = "quests"
    THEME = "theme"
    TRAINING = "training"


class WeaponTypeEnum(CaseInsensitiveEnum):
    MELEE = "melee"
    GUN = "gun"
    ENERGY = "energy"
    HEAVY = "heavy"


class WeaponSubtypeEnum(CaseInsensitiveEnum):
    BLUNT = "blunt"
    EDGED = "edged"
    POINTED = "pointed"
    PISTOL = "pistol"
    RIFLE = "rifle"
    SHOTGUN = "shotgun"
    AUTOMATIC = "automatic"
    EXPLOSIVE = "explosive"
    FLAMER = "flamer"
