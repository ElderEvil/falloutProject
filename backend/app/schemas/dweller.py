from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field
from sqlmodel import SQLModel

from app.models.dweller import DwellerBase
from app.schemas.common import (
    STATE_OF_BEING_TYPE,
    AgeGroupEnum,
    DeathCauseEnum,
    DwellerStatusEnum,
    FactionEnum,
    GenderEnum,
    RaceEnum,
    RarityEnum,
    SPECIALEnum,
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
    # TODO: Choose from inventory
    # outfit: str | None = None
    # weapon: str | None = None

    # Scene & Action
    pose: str | None = None
    background: str | None = None

    # Audio
    voice_line_text: str | None = None

    model_config = ConfigDict(use_enum_values=True)


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
    birth_date: datetime | None = None

    # SPECIAL stats
    strength: int
    perception: int
    endurance: int
    charisma: int
    intelligence: int
    agility: int
    luck: int

    # Relationships
    partner_id: UUID4 | None = None
    parent_1_id: UUID4 | None = None
    parent_2_id: UUID4 | None = None

    # TBD
    # job: str | None


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
