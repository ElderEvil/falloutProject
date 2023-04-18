from app.api.crud.base import CRUDBase
from app.api.models.weapon import Weapon, WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDBase[Weapon, WeaponCreate, WeaponUpdate]):
    ...


weapon = CRUDWeapon(Weapon)
