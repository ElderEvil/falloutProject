"""Queries for the durable per-vault bobblehead claims."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.collectible import VaultCollectible


class CRUDCollectible:
    async def get_by_vault_and_key(
        self, db_session: AsyncSession, vault_id: UUID, collectible_key: str
    ) -> VaultCollectible | None:
        """The vault's claim for one collectible, or None when it is still out there."""
        result = await db_session.execute(
            select(VaultCollectible).where(
                VaultCollectible.vault_id == vault_id,
                VaultCollectible.collectible_key == collectible_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_dweller(
        self, db_session: AsyncSession, vault_id: UUID, dweller_id: UUID
    ) -> list[VaultCollectible]:
        """Claims found by one dweller in its current vault.

        Recycling keeps the dweller UUID across vaults, so both filters are required: ownership
        of the vault alone would expose a previous vault's claim.
        """
        result = await db_session.execute(
            select(VaultCollectible).where(
                VaultCollectible.vault_id == vault_id,
                VaultCollectible.finder_dweller_id == dweller_id,
            )
        )
        return list(result.scalars().all())


collectible_crud = CRUDCollectible()
