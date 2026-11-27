"""Junk item CRUD endpoints."""

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
    verify_item_access,
)
from app.core.game_data import get_static_game_data
from app.models.junk import Junk
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate
from app.schemas.responses import NULL_BODY_RESPONSES
from app.services.item_service import item_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/junk", tags=["Junk"], dependencies=[Depends(get_current_active_user)])


@router.post("/", response_model=JunkRead)
async def create_junk(
    junk_data: JunkCreate,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Junk:
    """Create a new junk item (administrators only)."""
    return await item_service.create_item(db_session, model=Junk, item_data=junk_data)


@router.get("/", response_model=list[JunkRead])
async def read_junk_list(
    vault_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[Junk]:
    """Retrieve a paginated list of a vault's junk inventory.

    Junk is vault inventory held in storage, not catalog data, so the vault is
    required rather than optional: an unscoped list would enumerate other
    players' materials.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await item_service.list_junk_for_vault(
        db_session, vault_id=vault_id, skip=pagination.skip, limit=pagination.limit
    )


@router.get("/{junk_id}", response_model=JunkRead)
async def read_junk(
    junk_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> Junk:
    """Retrieve a junk item by ID."""
    await verify_item_access(junk_id, Junk, user, db_session)
    return await item_service.get_item(db_session, model=Junk, item_id=junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
async def update_junk(
    junk_id: UUID,
    junk_data: JunkUpdate,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Junk:
    """Update a junk item (administrators only)."""
    return await item_service.update_item(db_session, model=Junk, item_id=junk_id, item_data=junk_data)


@router.delete("/{junk_id}", status_code=204)
async def delete_junk(
    junk_id: UUID,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> None:
    """Delete a junk item (administrators only)."""
    await item_service.delete_item(db_session, model=Junk, item_id=junk_id)


@router.get("/read_data/", response_model=list[JunkCreate])
async def read_junk_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[JunkCreate]:
    """Retrieve static junk item data."""
    return data_store.junk_items


@router.post("/{junk_id}/sell/", status_code=200, response_model=None, responses=NULL_BODY_RESPONSES)
async def sell_junk(
    junk_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> None:
    """Sell a junk item for caps."""
    await verify_item_access(junk_id, Junk, user, db_session)
    await item_service.sell_item(db_session, item_id=junk_id, model=Junk)
