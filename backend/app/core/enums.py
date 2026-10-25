"""Shared game-world enums (StrEnum) used across models, schemas, and services."""

from enum import StrEnum


class CaseInsensitiveEnum(StrEnum):
    @classmethod
    def _missing_(cls, value: object):
        if not isinstance(value, str):
            return None
        for member in cls:
            if member.lower() == value.lower():
                return member
        return None


class RadioModeEnum(StrEnum):
    RECRUITMENT = "recruitment"
    HAPPINESS = "happiness"


class VaultModeEnum(CaseInsensitiveEnum):
    """Per-vault difficulty mode.

    Chosen once at vault creation and immutable afterwards. ``SURVIVAL`` makes every
    dweller death permanent (immediate permanent-death memorial, no caps revival
    window). Stored as a plain string column, mirroring ``Vault.radio_mode``.
    """

    STANDARD = "standard"
    SURVIVAL = "survival"


class DwellerStatusEnum(CaseInsensitiveEnum):
    IDLE = "idle"
    WORKING = "working"
    EXPLORING = "exploring"
    QUESTING = "questing"
    TRAINING = "training"
    RESTING = "resting"
    FIGHTING = "fighting"
    DEAD = "dead"


class DwellerRosterFocus(CaseInsensitiveEnum):
    """Wire-only roster attention filters; not a persisted database enum."""

    LOW_HAPPINESS = "low_happiness"
    NEEDS_CARE = "needs_care"


class DeathCauseEnum(CaseInsensitiveEnum):
    HEALTH = "health"
    RADIATION = "radiation"
    INCIDENT = "incident"
    EXPLORATION = "exploration"
    COMBAT = "combat"
    EXILE = "exile"


class LifecycleEnum(CaseInsensitiveEnum):
    """Canonical dweller lifecycle — exactly one of these, independent of availability.

    ``WASTELAND`` is a living unaffiliated person, not a simulated journey; a departure
    is not a death and must never surface in the graveyard. ``is_dead`` /
    ``is_permanently_dead`` are compatibility projections over this state.
    """

    ALIVE = "alive"
    DEAD_REVIVABLE = "dead_revivable"
    DEAD_PERMANENT = "dead_permanent"
    WASTELAND = "wasteland"


class AvailabilityEnum(CaseInsensitiveEnum):
    """Canonical availability — where a person currently exists, not a death.

    Exactly one of these, enforced by the application (and later constraints). Death
    metadata exists only for ``DEAD_PERMANENT``; neither soft deletion nor a paid sale
    is a death. ``ARCHIVE`` is retired content; ``DEPARTURE`` is a private living departure.
    """

    VAULT = "vault"
    DEPARTURE = "departure"
    POOL = "pool"
    MARKET = "market"
    ARCHIVE = "archive"


class ContentProvenanceEnum(CaseInsensitiveEnum):
    """Who authored a person's identity content, for safe cross-vault reuse.

    Stored as VARCHAR (not a PostgreSQL enum): only system-authored or curated content
    may be reused. ``None`` means unknown provenance and defaults to private departure.
    """

    CURATED = "curated"
    GENERATED = "generated"
    PLAYER_EDITED = "player_edited"


class RarityEnum(CaseInsensitiveEnum):
    COMMON = "common"
    RARE = "rare"
    LEGENDARY = "legendary"


class ExpeditionRunStatus(StrEnum):
    """Status of one expedition-site attempt."""

    IN_ROOM = "in_room"
    RETREATED = "retreated"
    CLEARED = "cleared"
    DIED = "died"


class ObjectiveCategoryEnum(CaseInsensitiveEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    ACHIEVEMENT = "achievement"
    STARTER = "starter"


class SPECIALEnum(CaseInsensitiveEnum):
    STRENGTH = "strength"
    PERCEPTION = "perception"
    ENDURANCE = "endurance"
    CHARISMA = "charisma"
    INTELLIGENCE = "intelligence"
    AGILITY = "agility"
    LUCK = "luck"


#: Canonical SPECIAL attribute names in S.P.E.C.I.A.L. order.
SPECIAL_STATS: tuple[str, ...] = tuple(stat.value for stat in SPECIALEnum)

#: SPECIAL member -> canonical lowercase attribute name (single source of truth).
STAT_BY_SPECIAL: dict[SPECIALEnum, str] = {stat: stat.value for stat in SPECIALEnum}

#: Single-letter S.P.E.C.I.A.L. initial -> canonical lowercase attribute name.
STAT_BY_LETTER: dict[str, str] = {stat.name[0]: stat.value for stat in SPECIALEnum}


class GenderEnum(CaseInsensitiveEnum):
    MALE = "male"
    FEMALE = "female"


class AgeGroupEnum(CaseInsensitiveEnum):
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"
    ELDER = "elder"


#: Grown-up age groups for work, combat, exploration and auto-assignment.
#: Breeding stays ADULT-only; prefer this set over `== ADULT` so a new
#: adult-tier group is never silently locked out of a gameplay gate.
ADULT_AGE_GROUPS: frozenset[AgeGroupEnum] = frozenset({AgeGroupEnum.ADULT, AgeGroupEnum.ELDER})


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
    BROTHERHOOD_OF_STEEL = "brotherhood_of_steel"
    ENCLAVE = "enclave"
    MINUTEMEN = "minutemen"
    RAIDERS = "raiders"
    SUPER_MUTANT_TRIBE = "super_mutant_tribe"
    CHILDREN_OF_ATOM = "children_of_atom"
    THE_INSTITUTE = "the_institute"
    RAILROAD = "railroad"
    NCR = "ncr"
    CAESARS_LEGION = "caesars_legion"


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
    MISC = "misc"
    WEAPON = "weapon"
    OUTFIT = "outfit"
    JUNK = "junk"
    CONSUMABLE = "consumable"
    LUNCHBOX = "lunchbox"
    PET = "pet"
    DWELLER = "dweller"


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
    RESPONSE = "response"


class ArenaMode(CaseInsensitiveEnum):
    DUEL = "duel"
    BRAWL = "brawl"
    TRAINING = "training"
    HUNT = "hunt"


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


class PlaceKindEnum(StrEnum):
    """Canonical world-registry entry kind, used as the PostgreSQL `placekind` type."""

    PLACE = "place"
    VAULT = "vault"


class LocationTypeEnum(StrEnum):
    """Type of wasteland location — per-vault fog classification."""

    ORIGIN = "origin"
    VISITED = "visited"
    DISCOVERY = "discovery"
    HOME_VAULT = "home_vault"


class DwellerLocationRelationEnum(StrEnum):
    """How a dweller relates to a world location."""

    ORIGIN = "origin"
    VISITED = "visited"


class HazardTeam(CaseInsensitiveEnum):
    """A standing hazard-response team a dweller earns a place on.

    Membership is earned from service, never assigned: a dweller qualifies by
    fighting incidents of the team's hazard (see ``models/incident.py`` for the
    type mapping and ``services/hazard_team_service.py`` for the rule).
    """

    FIRE = "fire"
    RADIATION = "radiation"


class DamageChannel(StrEnum):
    """The damage channel a dweller can reduce; each channel has its own source set.

    Resolved once per dweller per channel by ``utils/damage_reductions.py``.
    """

    PHYSICAL = "physical"
    FIRE = "fire"
    RADIATION = "radiation"


STATE_OF_BEING_TYPE = GhoulFeralnessEnum | SuperMutantMutationEnum | SynthTypeEnum


class OAuthProviderEnum(StrEnum):
    """External identity providers supported by the sign-in flow."""

    GOOGLE = "google"
    GITHUB = "github"
