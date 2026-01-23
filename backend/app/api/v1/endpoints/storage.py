"""Storage management endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.crud import storage as crud_storage
from app.db.session import get_async_session
from app.schemas.storage import StorageSpaceResponse

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
