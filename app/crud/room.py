from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    async def create_with_vault_id(self, db_session: AsyncSession, obj_in: RoomCreate, vault_id: UUID4) -> Room:
        obj_data = obj_in.model_dump()
        obj_data["vault_id"] = vault_id
        obj_in = RoomCreate(**obj_data)
        return await super().create(db_session, obj_in)

    async def build(self, *, db_session: AsyncSession, obj_in: RoomCreate):
        obj_data = obj_in.model_dump()
        obj_data["vault_id"] = obj_in.vault_id
        obj_in = RoomCreate(**obj_data)
        return await super().create(db_session, obj_in)


room = CRUDRoom(Room)
