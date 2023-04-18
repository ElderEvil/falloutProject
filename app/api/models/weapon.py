from enum import Enum

from sqlmodel import Field

from app.api.models.item import ItemBase, ItemUpdate


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
