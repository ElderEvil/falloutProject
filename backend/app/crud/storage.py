"""Storage CRUD operations for managing vault storage space."""

import logging

from pydantic import UUID4
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.storage import Storage, StorageBase
from app.models.weapon import Weapon

logger = logging.getLogger(__name__)


class CRUDStorage(CRUDBase[Storage, StorageBase, StorageBase]):
    """CRUD operations for Storage with utility methods."""

    async def count_items(self, db_session: AsyncSession, storage_id: UUID4) -> int:
        """Count total items in storage (weapons + outfits + junk)."""
        # Count weapons
        weapons_result = await db_session.execute(
            select(func.count()).select_from(Weapon).where(Weapon.storage_id == storage_id)
        )
        weapons_count = weapons_result.scalar() or 0

        # Count outfits
        outfits_result = await db_session.execute(
            select(func.count()).select_from(Outfit).where(Outfit.storage_id == storage_id)
        )
        outfits_count = outfits_result.scalar() or 0

        # Count junk
        junk_result = await db_session.execute(
            select(func.count()).select_from(Junk).where(Junk.storage_id == storage_id)
        )
        junk_count = junk_result.scalar() or 0

        total = weapons_count + outfits_count + junk_count

        logger.debug(
            "Counted storage items",
            extra={
                "storage_id": str(storage_id),
                "weapons": weapons_count,
                "outfits": outfits_count,
                "junk": junk_count,
                "total": total,
            },
        )

        return total

    async def get_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> Storage | None:
        """Get storage by vault ID."""
        result = await db_session.execute(select(self.model).where(self.model.vault_id == vault_id))
        return result.scalar_one_or_none()

    async def get_available_space(self, db_session: AsyncSession, storage_id: UUID4) -> int:
        """Get available storage space."""
        storage = await self.get(db_session, id=storage_id)
        if not storage:
            return 0

        used = await self.count_items(db_session, storage_id)
        available = max(0, storage.max_space - used)

        logger.debug(
            "Calculated available space",
            extra={
                "storage_id": str(storage_id),
                "max_space": storage.max_space,
                "used": used,
                "available": available,
            },
        )

        return available

    async def update_used_space(self, db_session: AsyncSession, storage_id: UUID4) -> Storage:
        """Update used_space field based on actual item count."""
        storage = await self.get(db_session, id=storage_id)
        if not storage:
            msg = f"Storage not found: {storage_id}"
            raise ValueError(msg)

        used = await self.count_items(db_session, storage_id)
        storage.used_space = used
        db_session.add(storage)

        logger.info(
            "Updated storage used_space",
            extra={
                "storage_id": str(storage_id),
                "used_space": used,
                "max_space": storage.max_space,
            },
        )

        return storage

    async def get_info(self, db_session: AsyncSession, storage_id: UUID4) -> dict:
        """Get comprehensive storage information."""
        storage = await self.get(db_session, id=storage_id)
        if not storage:
            return {
                "used_space": 0,
                "max_space": 0,
                "available_space": 0,
                "utilization_pct": 0.0,
            }

        used = await self.count_items(db_session, storage_id)
        max_space = storage.max_space
        available = max(0, max_space - used)
        utilization = (used / max_space * 100) if max_space > 0 else 0.0

        return {
            "used_space": used,
            "max_space": max_space,
            "available_space": available,
            "utilization_pct": round(utilization, 2),
        }

    async def get_all_items(
        self, db_session: AsyncSession, storage_id: UUID4
    ) -> dict[str, list[Weapon] | list[Outfit] | list[Junk]]:
        """Get all items in storage (weapons, outfits, junk)."""
        weapons_result = await db_session.execute(select(Weapon).where(Weapon.storage_id == storage_id))
        outfits_result = await db_session.execute(select(Outfit).where(Outfit.storage_id == storage_id))
        junk_result = await db_session.execute(select(Junk).where(Junk.storage_id == storage_id))

        return {
            "weapons": list(weapons_result.scalars().all()),
            "outfits": list(outfits_result.scalars().all()),
            "junk": list(junk_result.scalars().all()),
        }


# Global instance
storage = CRUDStorage(Storage)

# Backwards compatibility aliases
count_storage_items = storage.count_items
get_storage = storage.get
get_storage_by_vault = storage.get_by_vault
get_available_space = storage.get_available_space
update_used_space = storage.update_used_space
get_storage_info = storage.get_info
get_all_items = storage.get_all_items
