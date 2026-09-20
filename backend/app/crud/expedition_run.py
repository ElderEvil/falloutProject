"""CRUD operations for expedition runs."""

from datetime import datetime

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus


class CRUDExpeditionRun(CRUDBase[ExpeditionRun, ExpeditionRun, ExpeditionRun]):
    """CRUD operations for ExpeditionRun rows."""

    async def create_run(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        vault_id: UUID4,
        dweller_id: UUID4,
        site_id: str,
    ) -> ExpeditionRun:
        """Insert one run row for a fresh site entry."""
        run = ExpeditionRun(
            exploration_id=exploration_id,
            vault_id=vault_id,
            dweller_id=dweller_id,
            site_id=site_id,
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)
        return run

    async def get_open_for_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> ExpeditionRun | None:
        """Return the still-open run for an exploration, if any."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.exploration_id == exploration_id)
            .where(ExpeditionRun.status.in_([ExpeditionRunStatus.ENTERED, ExpeditionRunStatus.IN_ROOM]))
        )
        return result.scalars().first()

    async def get_recent_clear(
        self, db_session: AsyncSession, *, vault_id: UUID4, site_id: str, since: datetime
    ) -> ExpeditionRun | None:
        """Return a clear of this site by this vault since the given timestamp (anti-farm)."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.vault_id == vault_id)
            .where(ExpeditionRun.site_id == site_id)
            .where(ExpeditionRun.status == ExpeditionRunStatus.CLEARED)
            .where(ExpeditionRun.cleared_at >= since)
        )
        return result.scalars().first()


expedition_run = CRUDExpeditionRun(ExpeditionRun)
