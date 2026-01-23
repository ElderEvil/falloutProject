"""Storage CRUD operations for managing vault storage space."""

import logging

from pydantic import UUID4
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.weapon import Weapon

logger = logging.getLogger(__name__)


async def count_storage_items(db_session: AsyncSession, storage_id: UUID4) -> int:
    """
    Count total items in storage (weapons + outfits + junk).

    :param db_session: Database session
    :param storage_id: Storage ID
    :returns: Total item count
    """
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
    junk_result = await db_session.execute(select(func.count()).select_from(Junk).where(Junk.storage_id == storage_id))
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


async def get_storage(db_session: AsyncSession, storage_id: UUID4) -> Storage | None:
    """
    Get storage by ID.

    :param db_session: Database session
    :param storage_id: Storage ID
    :returns: Storage object or None
    """
    result = await db_session.execute(select(Storage).where(Storage.id == storage_id))
    return result.scalar_one_or_none()


async def get_storage_by_vault(db_session: AsyncSession, vault_id: UUID4) -> Storage | None:
    """
    Get storage by vault ID.

    :param db_session: Database session
    :param vault_id: Vault ID
    :returns: Storage object or None
    """
    result = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    return result.scalar_one_or_none()


async def get_available_space(db_session: AsyncSession, storage_id: UUID4) -> int:
    """
    Get available storage space.

    :param db_session: Database session
    :param storage_id: Storage ID
    :returns: Available space (max_space - used items)
    """
    storage = await get_storage(db_session, storage_id)
    if not storage:
        return 0

    used = await count_storage_items(db_session, storage_id)
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


async def update_used_space(db_session: AsyncSession, storage_id: UUID4) -> Storage:
    """
    Update used_space field based on actual item count.

    :param db_session: Database session
    :param storage_id: Storage ID
    :returns: Updated storage object
    """
    storage = await get_storage(db_session, storage_id)
    if not storage:
        msg = f"Storage not found: {storage_id}"
        raise ValueError(msg)

    used = await count_storage_items(db_session, storage_id)
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


async def get_storage_info(db_session: AsyncSession, storage_id: UUID4) -> dict:
    """
    Get comprehensive storage information.

    :param db_session: Database session
    :param storage_id: Storage ID
    :returns: Dict with used_space, max_space, available_space, utilization_pct
    """
    storage = await get_storage(db_session, storage_id)
    if not storage:
        return {
            "used_space": 0,
            "max_space": 0,
            "available_space": 0,
            "utilization_pct": 0.0,
        }

    used = await count_storage_items(db_session, storage_id)
    max_space = storage.max_space
    available = max(0, max_space - used)
    utilization = (used / max_space * 100) if max_space > 0 else 0.0

    return {
        "used_space": used,
        "max_space": max_space,
        "available_space": available,
        "utilization_pct": round(utilization, 2),
    }
