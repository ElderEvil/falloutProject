import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4, BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.crud import dweller as crud_dweller
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.db.session import get_async_session
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
    vault = await get_user_vault_or_403(vault_id, current_user, db_session)

    storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found for vault")

    items = await crud_storage.get_all_items(db_session, storage.id)

    logger.info(
        "Storage items retrieved",
        extra={
            "vault_id": str(vault_id),
            "user_id": str(current_user.id),
            "weapons_count": len(items["weapons"]),
            "outfits_count": len(items["outfits"]),
            "junk_count": len(items["junk"]),
        },
    )

    return StorageItemsResponse(
        weapons=[WeaponRead.model_validate(w) for w in items["weapons"]],
        outfits=[OutfitRead.model_validate(o) for o in items["outfits"]],
        junk=[JunkRead.model_validate(j) for j in items["junk"]],
    )


class MedicalTransferRequest(BaseModel):
    """Request schema for medical supply transfer."""

    dweller_id: UUID4
    stimpaks: int = 0
    radaways: int = 0


@router.post("/vault/{vault_id}/medical/transfer")
async def transfer_medical_supplies(
    vault_id: UUID4,
    request: MedicalTransferRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
) -> dict:
    """
    Transfer medical supplies from vault storage to a dweller's inventory.

    Dwellers can carry max 15 stimpaks and 15 radaways each.
    Requires ownership of the vault.
    """
    vault = await get_user_vault_or_403(vault_id, current_user, db_session)

    dweller = await crud_dweller.get(db_session, request.dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")
    if dweller.vault_id != vault.id:
        raise HTTPException(status_code=403, detail="Dweller does not belong to this vault")

    if request.stimpaks < 0 or request.radaways < 0:
        raise HTTPException(status_code=400, detail="Transfer amounts cannot be negative")

    if request.stimpaks == 0 and request.radaways == 0:
        raise HTTPException(status_code=400, detail="No items to transfer")

    vault_stimpaks = vault.stimpack or 0
    vault_radaways = vault.radaway or 0

    if request.stimpaks > vault_stimpaks:
        raise HTTPException(status_code=400, detail=f"Vault only has {vault_stimpaks} stimpaks")
    if request.radaways > vault_radaways:
        raise HTTPException(status_code=400, detail=f"Vault only has {vault_radaways} radaways")

    dweller_stimpaks = dweller.stimpack or 0
    dweller_radaways = dweller.radaway or 0

    max_per_dweller = 15
    if request.stimpaks + dweller_stimpaks > max_per_dweller:
        raise HTTPException(status_code=400, detail=f"Dweller can only carry {max_per_dweller} stimpaks")
    if request.radaways + dweller_radaways > max_per_dweller:
        raise HTTPException(status_code=400, detail=f"Dweller can only carry {max_per_dweller} radaways")

    new_vault_stimpaks = vault_stimpaks - request.stimpaks
    new_vault_radaways = vault_radaways - request.radaways
    new_dweller_stimpaks = dweller_stimpaks + request.stimpaks
    new_dweller_radaways = dweller_radaways + request.radaways

    await crud_vault.update(
        db_session,
        vault.id,
        obj_in={"stimpack": new_vault_stimpaks, "radaway": new_vault_radaways},
    )

    await crud_dweller.update(
        db_session,
        request.dweller_id,
        obj_in={"stimpack": new_dweller_stimpaks, "radaway": new_dweller_radaways},
    )

    logger.info(
        "Medical supplies transferred",
        extra={
            "vault_id": str(vault_id),
            "dweller_id": str(request.dweller_id),
            "stimpaks_transferred": request.stimpaks,
            "radaways_transferred": request.radaways,
            "user_id": str(current_user.id),
        },
    )

    return {
        "stimpaks": new_dweller_stimpaks,
        "radaways": new_dweller_radaways,
        "vault_stimpaks": new_vault_stimpaks,
        "vault_radaways": new_vault_radaways,
    }
