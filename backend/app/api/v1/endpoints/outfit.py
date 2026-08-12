"""Outfit item CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.game_data_deps import get_static_game_data
from app.crud.item_base import get_items_list
from app.db.session import get_async_session
from app.models.outfit import Outfit
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate
from app.schemas.responses import JunkListResponse
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/outfits", tags=["Outfit"])


@router.post("/", response_model=OutfitRead)
async def create_outfit(
    outfit_data: OutfitCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> OutfitRead:
    """Create a new outfit.

    Returns:
        The created outfit.
    """
    return await crud.outfit.create(db_session, outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    vault_id: UUID4 | None = None,
) -> list[OutfitRead]:
    """Retrieve a paginated list of outfits, optionally filtered by vault.

    Returns:
        List of outfits.
    """
    return await get_items_list(crud.outfit, db_session, Outfit, vault_id, skip, limit)


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]) -> OutfitRead:
    """Retrieve an outfit by ID.

    Returns:
        The requested outfit.
    """
    return await crud.outfit.get(db_session, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID4,
    outfit_data: OutfitUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OutfitRead:
    """Update an outfit.

    Returns:
        The updated outfit.
    """
    return await crud.outfit.update(db_session, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]) -> None:
    """Delete an outfit."""
    return await crud.outfit.delete(db_session, outfit_id)


@router.post("/{dweller_id}/equip/{outfit_id}", response_model=OutfitRead)
async def equip_outfit(
    dweller_id: UUID4, outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> OutfitRead:
    """Equip an outfit on a dweller.

    Returns:
        The equipped outfit.
    """
    return await crud.outfit.equip(db_session=db_session, item_id=outfit_id, dweller_id=dweller_id)


@router.post("/{outfit_id}/unequip/", status_code=200, response_model=None)
async def unequip_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]) -> None:
    """Unequip an outfit from a dweller."""
    await crud.outfit.unequip(db_session=db_session, item_id=outfit_id)


@router.post("/{outfit_id}/scrap/", response_model=JunkListResponse)
async def scrap_outfit(
    outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> JunkListResponse:
    """Scrap an outfit into junk items.

    Returns:
        List of junk items produced from scrapping.
    """
    junk_list = await crud.outfit.scrap(db_session=db_session, item_id=outfit_id)
    return JunkListResponse(junk=junk_list)


@router.post("/{outfit_id}/sell/", status_code=200, response_model=None)
async def sell_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]) -> None:
    """Sell an outfit for caps."""
    await crud.outfit.sell(db_session=db_session, item_id=outfit_id)


@router.get("/read_data/", response_model=list[OutfitCreate])
async def read_outfits_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[OutfitCreate]:
    """Retrieve static outfit data definitions.

    Returns:
        List of static outfit definitions.
    """
    return data_store.outfits
