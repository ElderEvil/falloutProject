from app.crud.base import CRUDBase
from app.models.weapon import Weapon, WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDBase[Weapon, WeaponCreate, WeaponUpdate]):
    ...


weapon = CRUDWeapon(Weapon)
