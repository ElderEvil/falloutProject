from app.models.weapon import WeaponBase
from app.schemas.common_schema import WeaponSubtype, WeaponType
from app.schemas.item import ItemUpdate


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
