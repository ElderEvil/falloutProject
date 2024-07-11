from app.crud.item_base import CRUDItem
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDItem[Weapon, WeaponCreate, WeaponUpdate]):
    pass


weapon = CRUDWeapon(Weapon)
