from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    async def create_with_vault_id(self, db_session: AsyncSession, obj_in: RoomCreate, vault_id: UUID4) -> Room:
        obj_data = obj_in.dict()
        obj_data["vault_id"] = vault_id
        obj_in = RoomCreate(**obj_data)
        return await super().create(db_session, obj_in)

    async def build(self, *, db_session: AsyncSession, obj_in: RoomCreate):
        obj_data = obj_in.dict()
        obj_data["vault_id"] = obj_in.vault_id
        obj_in = RoomCreate(**obj_data)
        return await super().create(db_session, obj_in)

    async def upgrade(self, *, db_session: AsyncSession, id: UUID4, obj_in: RoomUpdate):
        obj_data = obj_in.dict()
        db_obj = await self.get(db_session=db_session, id=id)
        obj_data["vault_id"] = obj_in.vault_id
        obj_in = RoomUpdate(**obj_data)
        return await super().update(db_session, db_obj.id, obj_in)


room = CRUDRoom(Room)
