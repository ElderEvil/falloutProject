from app.crud.base import CRUDBase
from app.models.room import Room, RoomCreate, RoomUpdate


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    ...


room = CRUDRoom(Room)
