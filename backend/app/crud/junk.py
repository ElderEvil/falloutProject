"""Junk (crafting material) CRUD."""

from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.junk import Junk
from app.models.storage import Storage
from app.schemas.junk import JunkCreate, JunkUpdate


class CRUDJunk(CRUDBase[Junk, JunkCreate, JunkUpdate]):
    """Junk always lives in storage; crafting consumes it from there."""

    async def get_in_storage(self, db_session: AsyncSession, storage_id: UUID4) -> list[Junk]:
        """Every junk row held by one storage."""
        result = await db_session.execute(select(Junk).where(Junk.storage_id == storage_id))
        return list(result.scalars().all())

    async def get_multi_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> Sequence[Junk]:
        """A vault's junk inventory: rows held by any storage belonging to that vault."""
        query = (
            select(Junk)
            .join(Storage, Junk.storage_id == Storage.id)
            .where(Storage.vault_id == vault_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db_session.execute(query)
        return result.scalars().all()


junk = CRUDJunk(Junk)
