"""Storage management endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.crud import storage as crud_storage
from app.db.session import get_async_session
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.junk import JunkRead
from app.schemas.outfit import OutfitRead
from app.schemas.storage import StorageItemsResponse, StorageSpaceResponse
from app.schemas.weapon import WeaponRead

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/vault/{vault_id}/space")
async def get_storage_space(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
) -> StorageSpaceResponse:
    """
    Get storage space information for a vault.

    Returns current used space, maximum space, available space, and utilization percentage.
    Requires ownership of the vault.
    """
    # Verify ownership
    vault = await get_user_vault_or_403(vault_id, current_user, db_session)

    # Get storage explicitly (avoid lazy load)
    storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found for vault")

    # Get storage info
    storage_info = await crud_storage.get_storage_info(db_session, storage.id)

    logger.info(
        "Storage space queried",
        extra={
            "vault_id": str(vault_id),
            "user_id": str(current_user.id),
            "used_space": storage_info["used_space"],
            "max_space": storage_info["max_space"],
        },
    )

    return StorageSpaceResponse(**storage_info)


@router.get("/vault/{vault_id}/items")
async def get_storage_items(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
) -> StorageItemsResponse:
    """
    Get all items stored in vault storage.

    Returns weapons, outfits, and junk items.
    Requires ownership of the vault.
    """
    # Verify ownership
    vault = await get_user_vault_or_403(vault_id, current_user, db_session)

    # Get storage explicitly
    storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found for vault")

    # Fetch all items
    weapons_result = await db_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))
    weapons = weapons_result.scalars().all()

    outfits_result = await db_session.execute(select(Outfit).where(Outfit.storage_id == storage.id))
    outfits = outfits_result.scalars().all()

    junk_result = await db_session.execute(select(Junk).where(Junk.storage_id == storage.id))
    junk = junk_result.scalars().all()

    logger.info(
        "Storage items retrieved",
        extra={
            "vault_id": str(vault_id),
            "user_id": str(current_user.id),
            "weapons_count": len(weapons),
            "outfits_count": len(outfits),
            "junk_count": len(junk),
        },
    )

    return StorageItemsResponse(
        weapons=[WeaponRead.model_validate(w) for w in weapons],
        outfits=[OutfitRead.model_validate(o) for o in outfits],
        junk=[JunkRead.model_validate(j) for j in junk],
    )
