from fastapi import HTTPException
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate, DwellerUpdate, DwellerCreateCommon
from app.tests.factory.dwellers import create_random_common_dweller


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    async def create_random(self, db_session: AsyncSession, obj_in: DwellerCreateCommon) -> Dweller:
        data = obj_in.model_dump()
        if data.get("rarity") == "common":
            data.update(**create_random_common_dweller(data.get("gender")))

        db_obj = Dweller(**data)
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        return db_obj

    def calculate_experience_required(self, dweller_obj: Dweller) -> int:
        return int(100 * 1.5**dweller_obj.level)

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int):
        dweller_obj.experience += amount
        experience_required = self.calculate_experience_required(dweller_obj)
        if dweller_obj.experience >= experience_required:
            dweller_obj.level += 1
            dweller_obj.experience -= experience_required
        db_session.add(dweller_obj)
        await db_session.commit()
        await db_session.refresh(dweller_obj)

    async def move_to_room(self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4) -> None:
        dweller_obj = await self.get(db_session, dweller_id)
        if dweller_obj.room_id == room_id:
            raise HTTPException(status_code=400, detail="Dweller is already in the room")
        dweller_obj.room_id = room_id
        db_session.add(dweller_obj)
        await db_session.commit()
        await db_session.refresh(dweller_obj)

    def is_alive(self, dweller_obj: Dweller) -> bool:
        return dweller_obj.health > 0

    def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> None:
        if self.is_alive(dweller_obj):
            raise HTTPException(status_code=400, detail="Cannot reanimate alive dweller")
        dweller_obj.health = dweller_obj.max_health
        db_session.add(dweller_obj)
        db_session.commit()


dweller = CRUDDweller(Dweller)
