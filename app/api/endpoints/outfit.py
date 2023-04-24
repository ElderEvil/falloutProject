from fastapi_crudrouter import SQLAlchemyCRUDRouter

from app.api.models.outfit import Outfit, OutfitRead, OutfitCreate, OutfitUpdate
from app.db.base import get_session

router = SQLAlchemyCRUDRouter(
    schema=OutfitRead,
    create_schema=OutfitCreate,
    update_schema=OutfitUpdate,
    db_model=Outfit,
    db=get_session,
    delete_all_route=False
)
