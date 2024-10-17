from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import UUID4
from sqlmodel import SQLModel, and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import User
from app.utils.exceptions import ResourceNotFoundException

ModelType = TypeVar("ModelType", bound=SQLModel)


class VaultActionsMixin(Generic[ModelType]):
    model: type[ModelType]

    async def get_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, id: UUID4, *, user: User | None = None
    ) -> ModelType:
        query = select(self.model).where(and_(self.model.id == id, self.model.vault_id == vault_id))
        if user:
            query = query.where(self.model.user_id == user.id)
        response = await db_session.execute(query)
        db_obj = response.scalar_one_or_none()
        if db_obj is None:
            raise ResourceNotFoundException(self.model, identifier=id)
        return db_obj

    async def get_multi_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, *, skip: int = 0, limit: int = 100, user: User | None = None
    ) -> Sequence[ModelType]:
        query = select(self.model).where(self.model.vault_id == vault_id).offset(skip).limit(limit)
        if user:
            query = query.where(self.model.user_id == user.id)

        response = await db_session.execute(query)
        return response.scalars().all()
