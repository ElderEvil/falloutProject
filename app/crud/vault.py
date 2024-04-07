from typing import Sequence

from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultUpdate


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(self, db_session: AsyncSession, *, user_id: int) -> Sequence[Vault]:
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalars().all()

    async def create_with_user_id(self, db_session: AsyncSession, obj_in: VaultCreate, user_id: UUID4) -> Vault:
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db_session, obj_in)

    @staticmethod
    async def _create_rooms(db_session: AsyncSession, rooms_in: Sequence[RoomCreate]) -> None:
        from app.crud.room import room

        for room_in in rooms_in:
            await room.create(db_session, room_in)

    async def initiate(
        self,
        db_session: AsyncSession,
        obj_in: VaultCreate,
        user_id: UUID4,
    ) -> Vault:
        from app.utils.static_data import game_data_store

        vault_db_obj = await self.create_with_user_id(db_session, obj_in, user_id)

        rooms = game_data_store.rooms
        rooms_in = []

        for room_in in rooms:
            if room_in.name == "Vault Door":
                room_in_data = room_in.model_dump()
                room_in_data["vault_id"] = vault_db_obj.id
                room_in_data["coordinate_x"] = 0
                room_in_data["coordinate_y"] = 0
                rooms_in.append(RoomCreate(**room_in_data))
            elif room_in.name == "Elevator":
                for i in range(3):
                    room_in_data = room_in.model_dump()
                    room_in_data["vault_id"] = vault_db_obj.id
                    room_in_data["coordinate_x"] = 1
                    room_in_data["coordinate_y"] = i
                    rooms_in.append(RoomCreate(**room_in_data))

        await self._create_rooms(db_session, rooms_in)
        return vault_db_obj


vault = CRUDVault(Vault)
