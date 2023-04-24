from fastapi_crudrouter import SQLAlchemyCRUDRouter

from app.api.models.weapon import Weapon, WeaponRead, WeaponCreate, WeaponUpdate
from app.db.base import get_session

router = SQLAlchemyCRUDRouter(
    schema=WeaponRead,
    create_schema=WeaponCreate,
    update_schema=WeaponUpdate,
    db_model=Weapon,
    db=get_session,
    delete_all_route=False,
    get_one_route=False
)
