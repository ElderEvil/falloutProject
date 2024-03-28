from typing import TYPE_CHECKING
from pydantic import field_validator, UUID4
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.dweller import Dweller
from app.models.item import ItemBase
from app.schemas.common import WeaponSubtype, WeaponType

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class WeaponBase(ItemBase):
    weapon_type: WeaponType
    weapon_subtype: WeaponSubtype
    stat: str
    damage_min: int = Field(ge=0)
    damage_max: int = Field(ge=1)

    _MELEE_SUBTYPES = (WeaponSubtype.blunt, WeaponSubtype.edged, WeaponSubtype.pointed)
    _GUN_SUBTYPES = (WeaponSubtype.pistol, WeaponSubtype.rifle, WeaponSubtype.shotgun)
    _ENERGY_SUBTYPES = (WeaponSubtype.pistol, WeaponSubtype.rifle)
    _HEAVY_SUBTYPES = (WeaponSubtype.automatic, WeaponSubtype.flamer, WeaponSubtype.explosive)

    @classmethod
    @field_validator("weapon_subtype", mode="before")
    def validate_weapon_subtype(cls, v, values):  # noqa: ANN001
        weapon_type = values.get("weapon_type")
        message = f"Invalid weapon subtype for {weapon_type.value} weapon"

        match weapon_type:
            case WeaponType.melee:
                valid_subtypes = cls._MELEE_SUBTYPES
            case WeaponType.gun:
                valid_subtypes = cls._GUN_SUBTYPES
            case WeaponType.energy:
                valid_subtypes = cls._ENERGY_SUBTYPES
            case WeaponType.heavy:
                valid_subtypes = cls._HEAVY_SUBTYPES
            case _:
                return v

        if v not in valid_subtypes:
            raise ValueError(message)

        return v


class Weapon(BaseUUIDModel, WeaponBase, TimeStampMixin, table=True):
    dweller_id: UUID4 = Field(default=None, nullable=True, foreign_key="dweller.id")
    dweller: "Dweller" = Relationship(back_populates="weapon")
