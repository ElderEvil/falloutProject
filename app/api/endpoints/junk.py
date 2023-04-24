from fastapi_crudrouter import SQLAlchemyCRUDRouter

from app.api.models.junk import Junk, JunkRead, JunkCreate, JunkUpdate
from app.db.base import get_session

router = SQLAlchemyCRUDRouter(
    schema=JunkRead,
    create_schema=JunkCreate,
    update_schema=JunkUpdate,
    db_model=Junk,
    db=get_session,
    delete_all_route=False
)
