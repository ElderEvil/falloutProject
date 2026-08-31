from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator
from sqlmodel import SQLModel

from app.models.dweller import DwellerBase
from app.options.factions import FactionOption, faction_restrictions
from app.options.races import RaceOption
from app.schemas.common import (
    STATE_OF_BEING_TYPE,
    AgeGroupEnum,
    DeathCauseEnum,
    DwellerStatusEnum,
    FactionEnum,
    GenderEnum,
    RaceEnum,
    RarityEnum,
    RelationshipTypeEnum,
    SPECIALEnum,
    WeaponTypeEnum,
)
from app.schemas.outfit import OutfitRead
from app.schemas.room import RoomRead
from app.schemas.vault import VaultRead
from app.schemas.weapon import WeaponRead
from app.utils.partial import optional

LETTER_TO_STAT = {
    "S": "strength",
    "P": "perception",
    "E": "endurance",
    "C": "charisma",
    "A": "agility",
    "I": "intelligence",
    "L": "luck",
}

#: Canonical SPECIAL attribute names, in S.P.E.C.I.A.L. order.
SPECIAL_STATS: tuple[str, ...] = tuple(LETTER_TO_STAT.values())

STATS_RANGE_BY_RARITY = {
    RarityEnum.COMMON: (1, 3),
    RarityEnum.RARE: (3, 6),
    RarityEnum.LEGENDARY: (6, 10),
}


class DwellerCreateWithoutVaultID(DwellerBase):
    weapon: str | None = Field(default=None, max_length=32)
    outfit: str | None = Field(default=None, max_length=32)

    model_config = ConfigDict(use_enum_values=True)


class DwellerCreate(DwellerCreateWithoutVaultID):
    vault_id: UUID4


class DwellerVisualAttributes(BaseModel):
    """Unified schema for dweller visual attributes.

    Merges user-facing input fields (race, faction, equipment, scene)
    with AI-generated fields (height, appearance, build, clothing_style, etc.).
    All fields are optional — only populated fields are stored in the JSONB column.
    """

    # Identity
    race: RaceEnum | None = None
    faction: FactionEnum | None = None

    # Physical Attributes
    height: str | None = Field(None, description="Height: tall, average, short")
    build: str | None = Field(None, description="Build: slim, athletic, muscular, stocky, average, overweight")
    skin_tone: str | None = None
    eye_color: str | None = None
    age: int | None = Field(default=None, ge=18, le=80, description="Only for humans")
    state_of_being: STATE_OF_BEING_TYPE | None = Field(
        None, description="For non-humans: ghoul feralness, super mutant mutation, synth type"
    )

    # Appearance & Facial Features
    appearance: str | None = Field(None, description="Appearance: attractive, cute, average, unattractive")
    hair_style: str | None = Field(None, description="Hair style: short, long, curly, straight, wavy, bald")
    hair_color: str | None = None
    facial_hair: str | None = None
    makeup: str | None = None
    expression: str | None = None
    headgear: str | None = None
    distinguishing_features: list[str] | None = Field(
        None,
        description=(
            "Distinguishing features: scar, tattoo, mole, freckles, birthmark, piercing, eyepatch, prosthetic limb"
        ),
    )
    clothing_style: str | None = Field(None, description="Clothing style: casual, military, formal, rugged, eclectic")

    # Equipment
    accessory: str | None = None
    object_held: str | None = None

    # Scene & Action
    pose: str | None = None
    background: str | None = None

    # Audio
    voice_line_text: str | None = None
    voice_line_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_scalar_lists(cls, data: object) -> object:
        """Accept singleton scalar lists emitted by some local structured-output models."""
        if not isinstance(data, dict):
            return data

        normalized = {
            field: value[0]
            if field != "distinguishing_features" and isinstance(value, list) and len(value) == 1
            else value
            for field, value in data.items()
        }
        age = normalized.get("age")
        if isinstance(age, str) and age.removesuffix("s").isdigit():
            normalized["age"] = int(age.removesuffix("s"))
        return normalized

    @model_validator(mode="after")
    def validate_identity_combination(self) -> "DwellerVisualAttributes":
        """Reject race/faction pairs that the canonical options data excludes."""
        if self.race is None or self.faction is None:
            return self
        race = RaceOption(self.race)
        faction = FactionOption(self.faction)
        if faction not in faction_restrictions[race]:
            raise ValueError(f"Faction '{faction.value}' is not valid for race '{race.value}'")
        return self

    model_config = ConfigDict(use_enum_values=True)


class DwellerIdentityOptions(BaseModel):
    """Canonical identity choices used by dweller creation and editing clients."""

    races: list[str]
    factions_by_race: dict[str, list[str]]
    states_by_race: dict[str, list[str]]


# Backward-compatible alias for migration
DwellerVisualAttributesInput = DwellerVisualAttributes


class DwellerCreateCommonOverride(SQLModel):
    """Common random dweller overrides."""

    first_name: str | None = Field(default=None, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, min_length=2, max_length=32)
    gender: GenderEnum | None = Field(default=None)
    special_boost: SPECIALEnum | None = Field(default=None)
    visual_attributes: DwellerVisualAttributesInput | None = Field(default=None)


class DwellerRename(SQLModel):
    """Schema for renaming a dweller.

    Constraint intent: allow simple human names (words), disallow emoji/symbol spam.
    """

    # Letters (latin/cyrillic + accents), spaces, apostrophe, hyphen; 2-20 chars.
    first_name: str = Field(
        min_length=2,
        max_length=20,
        pattern=r"^[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё]+(?:[ '\-][A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё]+)*$",
    )


class DwellerReadLess(SQLModel):
    id: UUID4
    first_name: str
    last_name: str | None
    thumbnail_url: str | None
    level: int
    health: int
    max_health: int
    radiation: int
    happiness: int
    room_id: UUID4 | None = None
    status: DwellerStatusEnum
    is_adult: bool
    age_group: AgeGroupEnum
    gender: GenderEnum
    rarity: RarityEnum
    birth_date: datetime | None = None
    apprentice_stat: SPECIALEnum | None = None
    apprentice_started_at: datetime | None = None
    visual_attributes: DwellerVisualAttributes | None = None

    # SPECIAL stats
    strength: int
    perception: int
    endurance: int
    charisma: int
    intelligence: int
    agility: int
    luck: int

    # Relationships
    weapon_type: WeaponTypeEnum | None = None
    combat_power: float | None = None
    partner_id: UUID4 | None = None
    parent_1_id: UUID4 | None = None
    parent_2_id: UUID4 | None = None

    model_config = ConfigDict(from_attributes=True)

    # TBD


class DwellerRead(DwellerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class DwellerReadWithVaultID(DwellerRead):
    vault_id: UUID4


class DwellerReadWithRoomID(DwellerRead):
    room_id: UUID4

    model_config = ConfigDict(from_attributes=True)


class DwellerReadFull(DwellerRead):
    vault_id: UUID4
    vault: VaultRead
    room: RoomRead | None
    weapon: WeaponRead | None
    outfit: OutfitRead | None

    model_config = ConfigDict(from_attributes=True)


@optional()
class DwellerUpdate(DwellerBase):
    room_id: UUID4 | None = None
    visual_attributes: DwellerVisualAttributesInput | None = Field(default=None)


class DwellerDeadRead(SQLModel):
    """Schema for dead dweller list items."""

    id: UUID4
    first_name: str
    last_name: str | None
    level: int
    thumbnail_url: str | None
    death_timestamp: datetime | None
    death_cause: DeathCauseEnum | None
    is_permanently_dead: bool
    epitaph: str | None
    days_until_permanent: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DwellerReviveResponse(SQLModel):
    """Response schema for dweller revival."""

    dweller: DwellerRead
    caps_spent: int
    remaining_caps: int


class RevivalCostResponse(SQLModel):
    """Response schema for revival cost check."""

    dweller_id: UUID4
    dweller_name: str
    level: int
    revival_cost: int
    days_until_permanent: int | None
    can_afford: bool
    vault_caps: int


class LineageMember(SQLModel):
    """A single dweller in a lineage response."""

    id: UUID4
    first_name: str
    last_name: str | None
    generation: int
    is_dead: bool = False
    age_group: AgeGroupEnum = AgeGroupEnum.ADULT
    # Partner context — only populated for the `partners` array.
    relationship_type: RelationshipTypeEnum | None = None
    affinity: int | None = None


class LineageResponse(SQLModel):
    """Response schema for a dweller's computed family lineage."""

    dweller_id: UUID4
    generation: int
    parents: list[LineageMember]
    children: list[LineageMember]
    siblings: list[LineageMember]
    partners: list[LineageMember]
