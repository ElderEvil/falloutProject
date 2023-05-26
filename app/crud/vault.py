from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultUpdate


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(self, db: AsyncSession, *, user_id: int) -> list[Vault] | None:
        response = await db.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalars().all()

    async def create_with_user_id(self, db: AsyncSession, obj_in: VaultCreate, user_id: UUID4) -> Vault:
        obj_data = obj_in.dict()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db, obj_in)


vault = CRUDVault(Vault)
