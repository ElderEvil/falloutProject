from app.api.crud.base import CRUDBase
from app.api.models.room import Room, RoomCreate, RoomUpdate


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    ...


room = CRUDRoom(Room)
