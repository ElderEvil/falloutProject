"""Diplomatic filings: create, read the live one per direction, and answer; callers commit."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DiplomaticFilingKind, DiplomaticFilingStatus
from app.models.diplomatic_filing import DiplomaticFiling


class CRUDDiplomaticFiling:
    async def create(
        self,
        db_session: AsyncSession,
        *,
        from_vault_id: UUID,
        to_vault_id: UUID,
        kind: DiplomaticFilingKind,
        terms: dict[str, Any],
        expires_at: datetime,
    ) -> DiplomaticFiling:
        """File a PENDING offer; the caller commits (and pays any filing cost) around it."""
        filing = DiplomaticFiling(
            from_vault_id=from_vault_id,
            to_vault_id=to_vault_id,
            kind=kind,
            terms=terms,
            expires_at=expires_at,
        )
        db_session.add(filing)
        await db_session.flush()
        return filing

    async def get(
        self, db_session: AsyncSession, filing_id: UUID, *, for_update: bool = False
    ) -> DiplomaticFiling | None:
        """One filing; ``for_update`` serialises two answers arriving at the same instant."""
        query = select(DiplomaticFiling).where(DiplomaticFiling.id == filing_id)
        query = query.with_for_update() if for_update else query
        return (await db_session.execute(query)).scalar_one_or_none()

    async def get_pending(
        self,
        db_session: AsyncSession,
        *,
        from_vault_id: UUID,
        to_vault_id: UUID,
        kind: DiplomaticFilingKind,
    ) -> DiplomaticFiling | None:
        """The live filing of this kind in this direction, if one is still waiting.

        Ordering plus ``first`` rather than ``scalar_one_or_none``: a lost race that filed two
        rows must not raise here, and the older row is the one the recipient answers.
        """
        query = (
            select(DiplomaticFiling)
            .where(
                DiplomaticFiling.from_vault_id == from_vault_id,
                DiplomaticFiling.to_vault_id == to_vault_id,
                DiplomaticFiling.kind == kind.value,
                DiplomaticFiling.status == DiplomaticFilingStatus.PENDING.value,
            )
            .order_by(DiplomaticFiling.created_at.asc())
            .limit(1)
        )
        return (await db_session.execute(query)).scalars().first()

    async def list_for_vault(self, db_session: AsyncSession, *, vault_id: UUID) -> Sequence[DiplomaticFiling]:
        """The filing log for one vault, both directions, newest first."""
        query = (
            select(DiplomaticFiling)
            .where(or_(DiplomaticFiling.from_vault_id == vault_id, DiplomaticFiling.to_vault_id == vault_id))
            .order_by(DiplomaticFiling.created_at.desc())
        )
        return (await db_session.execute(query)).scalars().all()

    async def list_pending_outgoing(self, db_session: AsyncSession, *, vault_id: UUID) -> Sequence[DiplomaticFiling]:
        """Filings this vault has sent that are still waiting for an answer."""
        query = select(DiplomaticFiling).where(
            DiplomaticFiling.from_vault_id == vault_id,
            DiplomaticFiling.status == DiplomaticFilingStatus.PENDING.value,
        )
        return (await db_session.execute(query)).scalars().all()

    async def list_inbox(self, db_session: AsyncSession, *, vault_id: UUID) -> Sequence[DiplomaticFiling]:
        """Filings awaiting this vault's answer, earliest deadline first."""
        query = (
            select(DiplomaticFiling)
            .where(
                DiplomaticFiling.to_vault_id == vault_id,
                DiplomaticFiling.status == DiplomaticFilingStatus.PENDING.value,
            )
            .order_by(DiplomaticFiling.expires_at.asc())
        )
        return (await db_session.execute(query)).scalars().all()

    async def expire_overdue(self, db_session: AsyncSession, *, vault_id: UUID, now: datetime) -> Sequence[UUID]:
        """Stamp this vault's overdue PENDING filings EXPIRED; the caller commits."""
        query = select(DiplomaticFiling).where(
            or_(DiplomaticFiling.from_vault_id == vault_id, DiplomaticFiling.to_vault_id == vault_id),
            DiplomaticFiling.status == DiplomaticFilingStatus.PENDING.value,
            DiplomaticFiling.expires_at <= now,
        )
        filings = (await db_session.execute(query)).scalars().all()
        for filing in filings:
            filing.status = DiplomaticFilingStatus.EXPIRED
        if filings:
            await db_session.flush()
        return [filing.id for filing in filings]

    async def resolve(
        self,
        db_session: AsyncSession,
        filing: DiplomaticFiling,
        *,
        status: DiplomaticFilingStatus,
        responded_at: datetime,
    ) -> DiplomaticFiling:
        """Stamp an answer (ACCEPTED, REFUSED, VOID); the caller commits."""
        filing.status = status
        filing.responded_at = responded_at
        db_session.add(filing)
        await db_session.flush()
        return filing


diplomatic_filing = CRUDDiplomaticFiling()
