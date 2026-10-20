from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4, field_validator
from sqlalchemy import Index, event, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper
from sqlmodel import Field, Relationship

from app.core.enums import WeaponSubtypeEnum, WeaponTypeEnum
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.dweller import Dweller
from app.models.item import ItemBase

if TYPE_CHECKING:
    from app.models.storage import Storage


class WeaponBase(ItemBase):
    weapon_type: WeaponTypeEnum
    weapon_subtype: WeaponSubtypeEnum
    stat: str
    damage_min: int = Field(ge=0)
    damage_max: int = Field(ge=1)

    _MELEE_SUBTYPES = (WeaponSubtypeEnum.BLUNT, WeaponSubtypeEnum.EDGED, WeaponSubtypeEnum.POINTED)
    _GUN_SUBTYPES = (WeaponSubtypeEnum.PISTOL, WeaponSubtypeEnum.RIFLE, WeaponSubtypeEnum.SHOTGUN)
    _ENERGY_SUBTYPES = (WeaponSubtypeEnum.PISTOL, WeaponSubtypeEnum.RIFLE)
    _HEAVY_SUBTYPES = (WeaponSubtypeEnum.AUTOMATIC, WeaponSubtypeEnum.FLAMER, WeaponSubtypeEnum.EXPLOSIVE)

    @classmethod
    @field_validator("weapon_subtype", mode="before")
    def validate_weapon_subtype(cls, v, values):
        weapon_type = values.get("weapon_type")
        message = f"Invalid weapon subtype for {weapon_type.value} weapon"

        match weapon_type:
            case WeaponTypeEnum.MELEE:
                valid_subtypes = cls._MELEE_SUBTYPES
            case WeaponTypeEnum.GUN:
                valid_subtypes = cls._GUN_SUBTYPES
            case WeaponTypeEnum.ENERGY:
                valid_subtypes = cls._ENERGY_SUBTYPES
            case WeaponTypeEnum.HEAVY:
                valid_subtypes = cls._HEAVY_SUBTYPES
            case _:
                return v

        if v not in valid_subtypes:
            raise ValueError(message)

        return v

    def __str__(self):
        return f"{self.name}"


class Weapon(BaseUUIDModel, WeaponBase, TimeStampMixin, table=True):
    __table_args__ = (Index("ix_weapon_storage_trial", "storage_id", "last_maintenance_trial_at"),)
    last_maintenance_trial_at: datetime | None = Field(default=None)
    dweller_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="dweller.id", index=True)
    dweller: "Dweller" = Relationship(back_populates="weapon")
    storage_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="weapons")
    exploration_id: UUID4 | None = Field(
        default=None, nullable=True, foreign_key="exploration.id", index=True, ondelete="CASCADE"
    )


@event.listens_for(Weapon, "before_update")
def _reset_storage_trial_clock(_mapper: Mapper[Weapon], _connection: Connection, weapon: Weapon) -> None:
    """Every ORM return to storage starts a fresh hour, including collected held loot."""
    state = inspect(weapon)
    if weapon.storage_id is not None and state is not None and state.attrs.storage_id.history.has_changes():
        weapon.last_maintenance_trial_at = datetime.utcnow()
