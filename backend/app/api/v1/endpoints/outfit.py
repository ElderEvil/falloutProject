"""Outfit item CRUD endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import (
    CurrentActiveUser,
    CurrentSuperuser,
    get_current_active_user,
    get_user_vault_or_403,
    verify_dweller_access,
    verify_item_access,
)
from app.core.game_data import get_static_game_data
from app.crud.item_base import get_items_by_vault
from app.db.session import get_async_session
from app.models.outfit import Outfit
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate
from app.schemas.responses import JunkListResponse
from app.services.item_service import item_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/outfits", tags=["Outfit"], dependencies=[Depends(get_current_active_user)])


@router.post("/", response_model=OutfitRead)
async def create_outfit(
    outfit_data: OutfitCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Outfit:
    """Create a new outfit (administrators only).

    Returns:
        The created outfit.
    """
    return await crud.outfit.create(db_session, outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Outfit]:
    """Retrieve a paginated list of a vault's outfits.

    Every item lives in a vault's storage or on one of its dwellers, so the vault
    is required rather than optional: an unscoped list would enumerate other
    players' gear.

    Returns:
        List of outfits.

    Raises:
        AccessDeniedException: If the user doesn't own the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await get_items_by_vault(db_session, Outfit, vault_id, skip, limit)


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Outfit:
    """Retrieve an outfit by ID.

    Returns:
        The requested outfit.

    Raises:
        AccessDeniedException: If the user doesn't own the outfit's vault.
    """
    await verify_item_access(outfit_id, Outfit, user, db_session)
    return await crud.outfit.get(db_session, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID4,
    outfit_data: OutfitUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Outfit:
    """Update an outfit (administrators only).

    Returns:
        The updated outfit.
    """
    return await crud.outfit.update(db_session, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> None:
    """Delete an outfit (administrators only)."""
    await crud.outfit.delete(db_session, outfit_id)


@router.post("/{dweller_id}/equip/{outfit_id}", response_model=OutfitRead)
async def equip_outfit(
    dweller_id: UUID4,
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Outfit:
    """Equip an outfit on a dweller.

    Returns:
        The equipped outfit.

    Raises:
        AccessDeniedException: If the user owns neither the dweller nor the outfit.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    await verify_item_access(outfit_id, Outfit, user, db_session)
    return await crud.outfit.equip(db_session=db_session, item_id=outfit_id, dweller_id=dweller_id)


@router.post("/{outfit_id}/unequip/", status_code=200, response_model=None)
async def unequip_outfit(
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Unequip an outfit from a dweller.

    Raises:
        AccessDeniedException: If the user doesn't own the outfit's vault.
    """
    await verify_item_access(outfit_id, Outfit, user, db_session)
    await crud.outfit.unequip(db_session=db_session, item_id=outfit_id)


@router.post("/{outfit_id}/scrap/", response_model=JunkListResponse)
async def scrap_outfit(
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> JunkListResponse:
    """Scrap an outfit into junk items.

    Returns:
        List of junk items produced from scrapping.

    Raises:
        AccessDeniedException: If the user doesn't own the outfit's vault.
    """
    await verify_item_access(outfit_id, Outfit, user, db_session)
    junk_list = await crud.outfit.scrap(db_session=db_session, item_id=outfit_id)
    return JunkListResponse(junk=junk_list)


@router.post("/{outfit_id}/sell/", status_code=200, response_model=None)
async def sell_outfit(
    outfit_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Sell an outfit for caps.

    Raises:
        AccessDeniedException: If the user doesn't own the outfit's vault.
    """
    await verify_item_access(outfit_id, Outfit, user, db_session)
    await item_service.sell_item(db_session, item_id=outfit_id, model=Outfit)


@router.get("/read_data/", response_model=list[OutfitCreate])
async def read_outfits_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[OutfitCreate]:
    """Retrieve static outfit data definitions.

    Returns:
        List of static outfit definitions.
    """
    return data_store.outfits
