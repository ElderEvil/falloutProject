"""Outfit item CRUD endpoints."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentActiveUser,
    CurrentSuperuser,
    DBSession,
    PaginationParams,
    get_current_active_user,
    get_user_vault_or_403,
    verify_dweller_access,
    verify_item_access,
)
from app.core.game_data import get_static_game_data
from app.models.outfit import Outfit
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate
from app.schemas.responses import NULL_BODY_RESPONSES, JunkListResponse
from app.services.item_service import item_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/outfits", tags=["Outfit"], dependencies=[Depends(get_current_active_user)])


@router.post("/", response_model=OutfitRead)
async def create_outfit(
    outfit_data: OutfitCreate,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Outfit:
    """Create a new outfit (administrators only)."""
    return await item_service.create_item(db_session, model=Outfit, item_data=outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(
    vault_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[Outfit]:
    """Retrieve a paginated list of a vault's outfits.

    Every item lives in a vault's storage or on one of its dwellers, so the vault
    is required rather than optional: an unscoped list would enumerate other
    players' gear.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await item_service.list_items_for_vault(
        db_session, model=Outfit, vault_id=vault_id, skip=pagination.skip, limit=pagination.limit
    )


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(
    outfit_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> Outfit:
    """Retrieve an outfit by ID."""
    await verify_item_access(outfit_id, Outfit, user, db_session)
    return await item_service.get_item(db_session, model=Outfit, item_id=outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID,
    outfit_data: OutfitUpdate,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Outfit:
    """Update an outfit (administrators only)."""
    return await item_service.update_item(db_session, model=Outfit, item_id=outfit_id, item_data=outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(
    outfit_id: UUID,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> None:
    """Delete an outfit (administrators only)."""
    await item_service.delete_item(db_session, model=Outfit, item_id=outfit_id)


@router.post("/{dweller_id}/equip/{outfit_id}", response_model=OutfitRead)
async def equip_outfit(
    dweller_id: UUID,
    outfit_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> Outfit:
    """Equip an outfit on a dweller."""
    await verify_dweller_access(dweller_id, user, db_session)
    await verify_item_access(outfit_id, Outfit, user, db_session)
    return await item_service.equip_item(db_session, item_id=outfit_id, dweller_id=dweller_id, model=Outfit)


@router.post("/{outfit_id}/unequip/", status_code=200, response_model=None, responses=NULL_BODY_RESPONSES)
async def unequip_outfit(
    outfit_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> None:
    """Unequip an outfit from a dweller."""
    await verify_item_access(outfit_id, Outfit, user, db_session)
    await item_service.unequip_item(db_session, item_id=outfit_id, model=Outfit)


@router.post("/{outfit_id}/scrap/", response_model=JunkListResponse)
async def scrap_outfit(
    outfit_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> JunkListResponse:
    """Scrap an outfit into junk items."""
    await verify_item_access(outfit_id, Outfit, user, db_session)
    junk_list = await item_service.scrap_item(db_session, item_id=outfit_id, model=Outfit)
    return JunkListResponse(junk=junk_list)


@router.post("/{outfit_id}/sell/", status_code=200, response_model=None, responses=NULL_BODY_RESPONSES)
async def sell_outfit(
    outfit_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> None:
    """Sell an outfit for caps."""
    await verify_item_access(outfit_id, Outfit, user, db_session)
    await item_service.sell_item(db_session, item_id=outfit_id, model=Outfit)


@router.get("/read_data/", response_model=list[OutfitCreate])
async def read_outfits_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[OutfitCreate]:
    """Retrieve static outfit data definitions."""
    return data_store.outfits
