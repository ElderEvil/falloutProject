"""Queries for server-wide co-op world events and per-vault participation.

Lifecycle and contribution rules live in app.services.world_event_service; this module only
reads rows (and row-locks them) so the service stays query-free.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import WorldEventStatus
from app.crud.base import CRUDBase
from app.models.world_event import WorldEvent, WorldEventParticipation


class CRUDWorldEvent(CRUDBase[WorldEvent, None, None]):
    """Query access for the global world event and its participations."""

    async def get_current(self, db_session: AsyncSession) -> WorldEvent | None:
        """The ACTIVE event when one exists, else the newest finished event."""
        active = await db_session.execute(select(self.model).where(self.model.status == WorldEventStatus.ACTIVE))
        if event := active.scalar_one_or_none():
            return event

        finished = await db_session.execute(
            select(self.model)
            .where(col(self.model.status).in_([WorldEventStatus.COMPLETED, WorldEventStatus.EXPIRED]))
            .order_by(col(self.model.ends_at).desc())
            .limit(1)
        )
        return finished.scalar_one_or_none()

    async def get_for_update(self, db_session: AsyncSession, event_id: UUID) -> WorldEvent | None:
        """One event row locked FOR UPDATE, or None when missing; refreshes past the identity map."""
        result = await db_session.execute(
            select(self.model)
            .where(self.model.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_next_scheduled(self, db_session: AsyncSession, *, at: datetime) -> WorldEvent | None:
        """The earliest SCHEDULED event whose window has opened, or None."""
        result = await db_session.execute(
            select(self.model)
            .where(
                self.model.status == WorldEventStatus.SCHEDULED,
                col(self.model.starts_at) <= at,
            )
            .order_by(col(self.model.starts_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_participation(
        self, db_session: AsyncSession, event_id: UUID, vault_id: UUID
    ) -> WorldEventParticipation | None:
        """One vault's participation row, or None when it never contributed."""
        result = await db_session.execute(
            select(WorldEventParticipation).where(
                WorldEventParticipation.world_event_id == event_id,
                WorldEventParticipation.vault_id == vault_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_participation_for_update(
        self, db_session: AsyncSession, event_id: UUID, vault_id: UUID
    ) -> WorldEventParticipation | None:
        """One participation row locked FOR UPDATE, or None.

        The unique (event, vault) constraint means this row lock serializes every
        contribution and claim for that vault.
        """
        result = await db_session.execute(
            select(WorldEventParticipation)
            .where(
                WorldEventParticipation.world_event_id == event_id,
                WorldEventParticipation.vault_id == vault_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_participations(
        self, db_session: AsyncSession, event_id: UUID, limit: int = 50
    ) -> list[WorldEventParticipation]:
        """Participations for one event, largest contributor first."""
        result = await db_session.execute(
            select(WorldEventParticipation)
            .where(WorldEventParticipation.world_event_id == event_id)
            .order_by(col(WorldEventParticipation.contribution).desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def totals(self, db_session: AsyncSession, event_id: UUID) -> tuple[int, int]:
        """(distinct participating vaults, summed contributions) for one event."""
        result = await db_session.execute(
            select(
                func.count(func.distinct(col(WorldEventParticipation.vault_id))),
                func.coalesce(func.sum(WorldEventParticipation.contribution), 0),
            ).where(WorldEventParticipation.world_event_id == event_id)
        )
        participants, contributed = result.one()
        return int(participants), int(contributed)


world_event = CRUDWorldEvent(WorldEvent)
