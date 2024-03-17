from app.crud.base import CRUDBase
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDBase[Weapon, WeaponCreate, WeaponUpdate]): ...


weapon = CRUDWeapon(Weapon)
