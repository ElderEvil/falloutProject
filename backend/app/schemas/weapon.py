from dataclasses import dataclass
from datetime import datetime

from pydantic import UUID4

from app.core.enums import RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.models.weapon import WeaponBase
from app.utils.partial import optional


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
    storage_id: UUID4 | None = None


class WeaponRead(WeaponBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
    # Read-time workshop summary; weapons carry no flavor-text column.
    description: str | None = None


@optional()
class WeaponUpdate(WeaponBase):
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
