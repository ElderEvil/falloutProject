"""Reads and the ordered pair key for vault relations; CRUD flushes, callers commit."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import VaultRelationStatus
from app.models.vault_relation import VaultRelation


def ordered_pair(first_vault_id: UUID, second_vault_id: UUID) -> tuple[UUID, UUID]:
    """Order a vault pair the way ``vaultrelation`` keys it, so either side reads one row."""
    return (first_vault_id, second_vault_id) if first_vault_id < second_vault_id else (second_vault_id, first_vault_id)


class CRUDVaultRelation:
    async def get_pair(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID,
        other_vault_id: UUID,
        for_update: bool = False,
    ) -> VaultRelation | None:
        """The pair's relation row, whichever direction the caller names the two vaults."""
        low, high = ordered_pair(vault_id, other_vault_id)
        query = select(VaultRelation).where(VaultRelation.vault_a_id == low, VaultRelation.vault_b_id == high)
        query = query.with_for_update() if for_update else query
        return (await db_session.execute(query)).scalar_one_or_none()

    async def get_or_create(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID,
        other_vault_id: UUID,
        status: VaultRelationStatus = VaultRelationStatus.UNMET,
        for_update: bool = False,
    ) -> VaultRelation:
        """Fetch the pair row, inserting one at ``status`` if none exists; the caller commits."""
        existing = await self.get_pair(
            db_session, vault_id=vault_id, other_vault_id=other_vault_id, for_update=for_update
        )
        if existing is not None:
            return existing
        low, high = ordered_pair(vault_id, other_vault_id)
        relation = VaultRelation(vault_a_id=low, vault_b_id=high, status=status)
        db_session.add(relation)
        await db_session.flush()
        return relation

    async def list_for_vault(
        self, db_session: AsyncSession, *, vault_id: UUID, statuses: Sequence[VaultRelationStatus] | None = None
    ) -> Sequence[VaultRelation]:
        """Every relation this vault is part of, newest first, optionally filtered by status."""
        query = (
            select(VaultRelation)
            .where(or_(VaultRelation.vault_a_id == vault_id, VaultRelation.vault_b_id == vault_id))
            .order_by(VaultRelation.created_at.desc())
        )
        if statuses is not None:
            query = query.where(VaultRelation.status.in_([status.value for status in statuses]))
        return (await db_session.execute(query)).scalars().all()

    async def list_by_status(self, db_session: AsyncSession, *, status: VaultRelationStatus) -> Sequence[VaultRelation]:
        """Every relation currently at ``status``, for the tick pass that ages a ladder rung."""
        query = select(VaultRelation).where(VaultRelation.status == status.value)
        return (await db_session.execute(query)).scalars().all()


vault_relation = CRUDVaultRelation()
