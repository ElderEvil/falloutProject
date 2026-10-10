"""CRUD operations for per-vault crafting-recipe unlock progress."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.vault_recipe_unlock import VaultRecipeUnlock


class CRUDVaultRecipeUnlock(CRUDBase[VaultRecipeUnlock, None, None]):
    """Queries and progress writes for gated recipes."""

    async def get_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, item_type: str, recipe_name: str
    ) -> VaultRecipeUnlock | None:
        result = await db_session.execute(
            select(VaultRecipeUnlock).where(
                VaultRecipeUnlock.vault_id == vault_id,
                VaultRecipeUnlock.item_type == item_type,
                VaultRecipeUnlock.recipe_name == recipe_name,
            )
        )
        return result.scalars().first()

    async def unlocked_names(self, db_session: AsyncSession, vault_id: UUID4, item_type: str) -> set[str]:
        """Names of the vault's unlocked recipes of one workshop type."""
        result = await db_session.execute(
            select(VaultRecipeUnlock.recipe_name).where(
                VaultRecipeUnlock.vault_id == vault_id,
                VaultRecipeUnlock.item_type == item_type,
                col(VaultRecipeUnlock.unlocked_at).is_not(None),
            )
        )
        return set(result.scalars().all())

    async def record_scrap(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        item_type: str,
        recipe_name: str,
        threshold: int,
        source: str = "scrap",
    ) -> bool:
        """Count one scrap toward a recipe and report whether it just unlocked it.

        The caller holds a transaction-scoped advisory lock for this
        (vault, item, recipe) counter, so the read-modify-write cannot interleave
        across worker processes; the event bus already serializes scraps within one
        process. Counting stops once unlocked.
        """
        row = await self.get_for_vault(db_session, vault_id, item_type, recipe_name)
        if row is None:
            row = VaultRecipeUnlock(
                vault_id=vault_id,
                item_type=item_type,
                recipe_name=recipe_name,
                progress=0,
                source=source,
            )
            db_session.add(row)

        if row.unlocked_at is not None:
            return False

        row.progress += 1
        newly_unlocked = row.progress >= threshold
        if newly_unlocked:
            row.unlocked_at = datetime.utcnow()
        db_session.add(row)
        return newly_unlocked


vault_recipe_unlock = CRUDVaultRecipeUnlock(VaultRecipeUnlock)
