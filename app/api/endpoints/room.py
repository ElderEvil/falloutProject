from fastapi_crudrouter import SQLAlchemyCRUDRouter

from app.api.models.room import Room, RoomRead, RoomCreate, RoomUpdate
from app.db.base import get_session

router = SQLAlchemyCRUDRouter(
    schema=RoomRead,
    create_schema=RoomCreate,
    update_schema=RoomUpdate,
    db_model=Room,
    db=get_session,
    delete_all_route=False,
    get_one_route=False
)
