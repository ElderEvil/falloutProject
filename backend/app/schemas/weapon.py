from dataclasses import dataclass
from uuid import UUID

from app.core.enums import RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.models.weapon import WeaponBase
from app.utils.partial import optional
from app.utils.serialize_types import UTCDateTimeJSON


@dataclass(frozen=True, slots=True)
class LadderEntry:
    """Immutable, normalized catalog variant used by maintenance and the item factory."""

    name: str
    rarity: RarityEnum
    value: int | None
    weapon_type: WeaponTypeEnum
    weapon_subtype: WeaponSubtypeEnum
    stat: str
    damage_min: int
    damage_max: int


class WeaponCreate(WeaponBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID | None = None


class WeaponRead(WeaponBase):
    id: UUID
    created_at: UTCDateTimeJSON
    updated_at: UTCDateTimeJSON
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
    # Read-time workshop summary; weapons carry no flavor-text column.
    description: str | None = None


@optional()
class WeaponUpdate(WeaponBase):
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
