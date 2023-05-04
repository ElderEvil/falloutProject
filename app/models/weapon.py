from pydantic import validator
from sqlmodel import Field

from app.models.item import ItemBase
from app.schemas.common_schema import WeaponSubtype, WeaponType


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
    @validator("weapon_subtype", pre=True)
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


class Weapon(WeaponBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    def __str__(self):
        return (
            f"{'🗡️' if self.weapon_type == WeaponType.melee else '🔫'}{self.name}"
            f" 💥{self.damage_min}-{self.damage_max}"
            f" 🪙{self.value}"
            f" 💎{self.rarity.name.title()}"
        )
