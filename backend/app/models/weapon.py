from typing import TYPE_CHECKING

from pydantic import UUID4, field_validator
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.dweller import Dweller
from app.models.item import ItemBase
from app.schemas.common import WeaponSubtypeEnum, WeaponTypeEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller
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
    dweller_id: UUID4 = Field(default=None, nullable=True, foreign_key="dweller.id")
    dweller: "Dweller" = Relationship(back_populates="weapon")
    storage_id: UUID4 = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="weapons")
