from app.crud.item_base import CRUDEquippableItem
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDEquippableItem[Weapon, WeaponCreate, WeaponUpdate]):
    pass


weapon = CRUDWeapon(Weapon)
