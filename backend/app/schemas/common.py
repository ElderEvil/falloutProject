from datetime import UTC, datetime
from enum import StrEnum


def _format_utc_datetime(value: datetime) -> str:
    """Format a single datetime as a UTC ``Z``-suffixed ISO-8601 string."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize a required datetime as an unambiguous UTC string.

    The application stores timestamps as naive UTC, so this helper treats
    tz-naive values as UTC and converts tz-aware values to UTC before
    emitting an ISO-8601 string ending with ``Z``.
    """
    return _format_utc_datetime(value)


def serialize_optional_utc_datetime(value: datetime | None) -> str | None:
    """Serialize an optional datetime as an unambiguous UTC string."""
    if value is None:
        return None
    return _format_utc_datetime(value)


class CaseInsensitiveEnum(StrEnum):
    @classmethod
    def _missing_(cls, value: str):
        for member in cls:
            if member.lower() == value.lower():
                return member
        return None


class GameStatusEnum(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class RadioModeEnum(StrEnum):
    RECRUITMENT = "recruitment"
    HAPPINESS = "happiness"


class DwellerStatusEnum(CaseInsensitiveEnum):
    IDLE = "idle"
    WORKING = "working"
    EXPLORING = "exploring"
    QUESTING = "questing"
    TRAINING = "training"
    RESTING = "resting"
    FIGHTING = "fighting"
    DEAD = "dead"


class DeathCauseEnum(CaseInsensitiveEnum):
    HEALTH = "health"
    RADIATION = "radiation"
    INCIDENT = "incident"
    EXPLORATION = "exploration"
    COMBAT = "combat"


class RarityEnum(CaseInsensitiveEnum):
    COMMON = "common"
    RARE = "rare"
    LEGENDARY = "legendary"


class ObjectiveCategoryEnum(CaseInsensitiveEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    ACHIEVEMENT = "achievement"


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


class AgeGroupEnum(CaseInsensitiveEnum):
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"


class RelationshipTypeEnum(CaseInsensitiveEnum):
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    ROMANTIC = "romantic"
    PARTNER = "partner"
    MARRIED = "MARRIED"
    EX = "ex"


PARTNER_LINKED_STAGES: frozenset[RelationshipTypeEnum] = frozenset(
    {RelationshipTypeEnum.PARTNER, RelationshipTypeEnum.MARRIED}
)


class PregnancyStatusEnum(CaseInsensitiveEnum):
    PREGNANT = "pregnant"
    DELIVERED = "delivered"
    MISCARRIED = "miscarried"


class RaceEnum(CaseInsensitiveEnum):
    HUMAN = "human"
    GHOUL = "ghoul"
    SUPER_MUTANT = "super_mutant"
    SYNTH = "synth"


class FactionEnum(CaseInsensitiveEnum):
    NONE = "none"
    VAULT_DWELLER = "vault_dweller"
    BOS = "brotherhood_of_steel"
    ENCLAVE = "enclave"
    MINUTEMEN = "minutemen"
    RAIDERS = "raiders"
    SM_TRIBE = "super_mutant_tribe"
    COA = "children_of_atom"
    INSTITUTE = "the_institute"
    RAILROAD = "railroad"
    NCR = "ncr"
    LEGION = "caesars_legion"


class SynthTypeEnum(CaseInsensitiveEnum):
    GEN_1 = "gen_1"
    GEN_2 = "gen_2"
    GEN_3 = "gen_3"


class GhoulFeralnessEnum(CaseInsensitiveEnum):
    SANE = "sane"
    WILD = "wild"
    FERAL = "feral"


class SuperMutantMutationEnum(CaseInsensitiveEnum):
    MILD = "mild"
    AVERAGE = "average"
    BEHEMOTH = "behemoth"


class ItemTypeEnum(CaseInsensitiveEnum):
    WEAPON = "weapon"
    OUTFIT = "outfit"
    JUNK = "junk"


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
    ARENA = "arena"


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


class AIModelType(CaseInsensitiveEnum):
    CHATGPT = "ChatGPT"
    DALLE = "DALL-E"
    OTHER = "Other"


class ObjectiveKindEnum(StrEnum):
    ANY = "Any"
    ASSIGN = "assign"
    COLLECT = "collect"


STATE_OF_BEING_TYPE = GhoulFeralnessEnum | SuperMutantMutationEnum | SynthTypeEnum
