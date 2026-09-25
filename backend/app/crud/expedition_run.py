"""CRUD operations for expedition runs."""

from datetime import datetime

from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.exploration import OPEN_STATUSES, TERMINAL_STATUSES, ExpeditionRun
from app.utils.exceptions import ResourceConflictException


def _violates_open_vault_site(error: IntegrityError) -> bool:
    """Return whether the integrity error came from the open vault+site index."""
    message = str(error.orig)
    return "uq_expeditionrun_open_vault_site" in message or (
        "expeditionrun.vault_id" in message and "expeditionrun.site_id" in message
    )


class CRUDExpeditionRun(CRUDBase[ExpeditionRun, ExpeditionRun, ExpeditionRun]):
    """CRUD operations for ExpeditionRun rows."""

    async def create_run(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        vault_id: UUID4,
        site_id: str,
    ) -> ExpeditionRun:
        """Insert one run row for a fresh site entry."""
        run = ExpeditionRun(
            exploration_id=exploration_id,
            vault_id=vault_id,
            site_id=site_id,
        )
        db_session.add(run)
        try:
            await db_session.flush()
        except IntegrityError as e:
            await db_session.rollback()
            if _violates_open_vault_site(e):
                raise ResourceConflictException(f"{site_id} already has an open expedition run") from e
            raise ResourceConflictException("This exploration already has an open expedition run") from e
        await db_session.refresh(run)
        return run

    async def get_open_for_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> ExpeditionRun | None:
        """Return the still-open run for an exploration, if any."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.exploration_id == exploration_id)
            .where(ExpeditionRun.status.in_(OPEN_STATUSES))
        )
        return result.scalars().first()

    async def get_open_for_exploration_for_update(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> ExpeditionRun | None:
        """Return the open run locked FOR UPDATE so concurrent resolutions serialize."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.exploration_id == exploration_id)
            .where(ExpeditionRun.status.in_(OPEN_STATUSES))
            .with_for_update()
        )
        return result.scalars().first()

    async def get_open_for_vault_site(
        self, db_session: AsyncSession, *, vault_id: UUID4, site_id: str
    ) -> ExpeditionRun | None:
        """Return the still-open run for a vault+site, if any (exclusivity)."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.vault_id == vault_id)
            .where(ExpeditionRun.site_id == site_id)
            .where(ExpeditionRun.status.in_(OPEN_STATUSES))
        )
        return result.scalars().first()

    async def get_recent_terminal(
        self, db_session: AsyncSession, *, vault_id: UUID4, site_id: str, since: datetime
    ) -> ExpeditionRun | None:
        """Return a terminal run (CLEARED/RETREATED/DIED) of this site by this vault since the given timestamp."""
        result = await db_session.execute(
            select(ExpeditionRun)
            .where(ExpeditionRun.vault_id == vault_id)
            .where(ExpeditionRun.site_id == site_id)
            .where(ExpeditionRun.status.in_(TERMINAL_STATUSES))
            .where(ExpeditionRun.finished_at >= since)
        )
        return result.scalars().first()


expedition_run = CRUDExpeditionRun(ExpeditionRun)
