from enum import Enum

from pydantic import validator
from sqlmodel import Field

from app.models.item import ItemBase, ItemUpdate


class WeaponType(str, Enum):
    Melee = "Melee"
    Gun = "Gun"
    Energy = "Energy"
    Heavy = "Heavy"


class WeaponSubtype(str, Enum):
    Blunt = "Blunt"
    Edged = "Edged"
    Pointed = "Pointed"
    Pistol = "Pistol"
    Rifle = "Rifle"
    Shotgun = "Shotgun"
    Automatic = "Automatic"
    Explosive = "Explosive"
    Flamer = "Flamer"


class WeaponBase(ItemBase):
    weapon_type: WeaponType
    weapon_subtype: WeaponSubtype
    stat: str
    damage_min: int
    damage_max: int

    _MELEE_SUBTYPES = (WeaponSubtype.Blunt, WeaponSubtype.Edged, WeaponSubtype.Pointed)
    _GUN_SUBTYPES = (WeaponSubtype.Pistol, WeaponSubtype.Rifle, WeaponSubtype.Shotgun)
    _ENERGY_SUBTYPES = (WeaponSubtype.Pistol, WeaponSubtype.Rifle)
    _HEAVY_SUBTYPES = (WeaponSubtype.Automatic, WeaponSubtype.Flamer, WeaponSubtype.Explosive)

    @validator('weapon_subtype')
    def validate_weapon_subtype(cls, v, values):
        weapon_type = values.get('weapon_type')
        message = f"Invalid weapon subtype for {weapon_type.value} weapon"

        match weapon_type:
            case WeaponType.Melee:
                valid_subtypes = cls._MELEE_SUBTYPES
            case WeaponType.Gun:
                valid_subtypes = cls._GUN_SUBTYPES
            case WeaponType.Energy:
                valid_subtypes = cls._ENERGY_SUBTYPES
            case WeaponType.Heavy:
                valid_subtypes = cls._HEAVY_SUBTYPES
            case _:
                return v

        if v not in valid_subtypes:
            raise ValueError(message)

        return v


class Weapon(WeaponBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    def __str__(self):
        return f"{'🗡️' if self.weapon_type == WeaponType.Melee else '🔫'}{self.name}" \
               f" 💥{self.damage_min}-{self.damage_max}" \
               f" 🪙{self.value}" \
               f" 💎{self.rarity.name.title()}"


class WeaponCreate(WeaponBase):
    pass


class WeaponRead(WeaponBase):
    id: int


class WeaponUpdate(ItemUpdate):
    weapon_type: WeaponType | None = None
    weapon_subtype: WeaponSubtype | None = None
    stat: str | None = None
    damage_min: int | None = None
    damage_max: int | None = None
