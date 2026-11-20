"""CRUD for dweller memories: bounded, deduped facts a dweller knows about itself."""

from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller_memory import DwellerMemory


class CRUDDwellerMemory(CRUDBase[DwellerMemory, DwellerMemory, DwellerMemory]):
    async def list_for_dweller(
        self, db: AsyncSession, *, dweller_id: UUID, limit: int | None = None
    ) -> list[DwellerMemory]:
        """Newest first; the prompt budget is a LIMIT, not a later slice."""
        query = (
            select(DwellerMemory)
            .where(col(DwellerMemory.dweller_id) == dweller_id)
            .order_by(col(DwellerMemory.created_at).desc(), col(DwellerMemory.id).desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return list((await db.exec(query)).all())

    async def list_oldest_first(self, db: AsyncSession, *, dweller_id: UUID) -> list[DwellerMemory]:
        """Creation order, so eviction removes what the dweller learned first."""
        query = (
            select(DwellerMemory)
            .where(col(DwellerMemory.dweller_id) == dweller_id)
            .order_by(col(DwellerMemory.created_at).asc().nulls_first(), col(DwellerMemory.id).asc())
        )
        return list((await db.exec(query)).all())

    async def trim_to_cap(self, db: AsyncSession, *, dweller_id: UUID, cap: int) -> int:
        """Delete the oldest memories beyond ``cap``; returns how many were removed."""
        ordered = await self.list_oldest_first(db, dweller_id=dweller_id)
        excess = max(len(ordered) - cap, 0)
        for memory in ordered[:excess]:
            await db.delete(memory)
        if excess:
            await db.flush()
        return excess

    async def hashes_for(self, db: AsyncSession, *, dweller_id: UUID) -> dict[str, str]:
        """Hash -> stored fact, the dedupe baseline before an extraction runs."""
        return {memory.fact_hash: memory.fact for memory in await self.list_for_dweller(db, dweller_id=dweller_id)}


dweller_memory = CRUDDwellerMemory(DwellerMemory)
