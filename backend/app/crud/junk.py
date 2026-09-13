"""Junk (crafting material) CRUD."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.item_base import CRUDItem
from app.models.junk import Junk
from app.schemas.junk import JunkCreate, JunkUpdate


class CRUDJunk(CRUDItem[Junk, JunkCreate, JunkUpdate]):
    """Junk always lives in storage; crafting consumes it from there."""

    async def get_in_storage(self, db_session: AsyncSession, storage_id: UUID4) -> list[Junk]:
        """Every junk row held by one storage."""
        result = await db_session.execute(select(Junk).where(Junk.storage_id == storage_id))
        return list(result.scalars().all())


junk = CRUDJunk(Junk)
