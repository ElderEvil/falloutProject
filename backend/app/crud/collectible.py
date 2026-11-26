"""Queries for the durable per-vault bobblehead claims."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.collectible import VaultCollectible


class CRUDCollectible:
    async def revoke_finder_bonus(self, db_session: AsyncSession, *, dweller_id: UUID) -> None:
        """Stop every claim this finder owns from paying a bonus; the vaults keep the claims.

        Called where a dwelling clears ``collectible_bonus``/``magazine_boon`` (death, recycling).
        The bonus lives on the dweller, not the vault, so a claim in any vault stops paying. A
        claim stays in the list as found history, but readback must not promise a lost bonus.
        """
        await db_session.execute(
            update(VaultCollectible)
            .where(
                col(VaultCollectible.finder_dweller_id) == dweller_id,
                col(VaultCollectible.bonus_live).is_(True),
            )
            .values(bonus_live=False)
        )

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

    async def list_keys(self, db_session: AsyncSession, vault_id: UUID) -> list[str]:
        """Every collectible key this vault holds; the set bonus reads claims, never finders."""
        result = await db_session.execute(
            select(VaultCollectible.collectible_key).where(VaultCollectible.vault_id == vault_id)
        )
        return list(result.scalars().all())

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
