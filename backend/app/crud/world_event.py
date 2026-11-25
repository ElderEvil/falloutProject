"""Queries for world events and per-vault participation; rules live in world_event_service."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import WorldEventStatus
from app.crud.base import CRUDBase
from app.models.world_event import WorldEvent, WorldEventParticipation


class CRUDWorldEvent(CRUDBase[WorldEvent, None, None]):
    """Query access for world events and participations."""

    async def get_current(self, db_session: AsyncSession) -> WorldEvent | None:
        """The ACTIVE event, else the newest finished one."""
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

    async def get_claimable_for_vault(self, db_session: AsyncSession, vault_id: UUID) -> WorldEvent | None:
        """The newest COMPLETED event this vault took part in — what a claim targets.

        A claim must not follow the ACTIVE event: once the next event activates, a vault that
        contributed to the finished one can still collect its reward.
        """
        result = await db_session.execute(
            select(self.model)
            .join(WorldEventParticipation, col(WorldEventParticipation.world_event_id) == col(self.model.id))
            .where(
                self.model.status == WorldEventStatus.COMPLETED,
                col(WorldEventParticipation.vault_id) == vault_id,
            )
            .order_by(col(self.model.ends_at).desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_completed(self, db_session: AsyncSession) -> bool:
        """True when any event has ever completed; separates "too early" from "never took part"."""
        result = await db_session.execute(
            select(self.model.id).where(self.model.status == WorldEventStatus.COMPLETED).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_for_update(self, db_session: AsyncSession, event_id: UUID) -> WorldEvent | None:
        """FOR UPDATE, or None; populate_existing so a stale identity-map row cannot be returned."""
        result = await db_session.execute(
            select(self.model)
            .where(self.model.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_next_scheduled(self, db_session: AsyncSession, *, at: datetime) -> WorldEvent | None:
        """The earliest SCHEDULED event whose window has opened."""
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

    async def has_scheduled(self, db_session: AsyncSession) -> bool:
        """True when any future or due SCHEDULED row already exists."""
        result = await db_session.execute(
            select(self.model.id).where(self.model.status == WorldEventStatus.SCHEDULED).limit(1)
        )
        return result.scalar_one_or_none() is not None

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

        The unique (event, vault) key makes this lock serialize every contribution and claim
        for that vault.
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

    async def list_participant_vault_ids(self, db_session: AsyncSession, event_id: UUID) -> list[UUID]:
        """Every vault that contributed to one event, for completion fan-out."""
        result = await db_session.execute(
            select(col(WorldEventParticipation.vault_id)).where(WorldEventParticipation.world_event_id == event_id)
        )
        return list(result.scalars().all())

    async def participant_count(self, db_session: AsyncSession, event_id: UUID) -> int:
        """Distinct vaults that contributed to one event."""
        result = await db_session.execute(
            select(func.count(func.distinct(col(WorldEventParticipation.vault_id)))).where(
                WorldEventParticipation.world_event_id == event_id
            )
        )
        return int(result.scalar_one())


world_event = CRUDWorldEvent(WorldEvent)
