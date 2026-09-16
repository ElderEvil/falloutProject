"""Junk item CRUD endpoints."""

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
    verify_item_access,
)
from app.core.game_data import get_static_game_data
from app.db.session import get_async_session
from app.models.junk import Junk
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate
from app.services.item_service import item_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/junk", tags=["Junk"], dependencies=[Depends(get_current_active_user)])


@router.post("/", response_model=JunkRead)
async def create_junk(
    junk_data: JunkCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Junk:
    """Create a new junk item (administrators only).

    Returns:
        The created junk item.
    """
    return await crud.junk.create(db_session, junk_data)


@router.get("/", response_model=list[JunkRead])
async def read_junk_list(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Junk]:
    """Retrieve a paginated list of a vault's junk inventory.

    Junk is vault inventory held in storage, not catalog data, so the vault is
    required rather than optional: an unscoped list would enumerate other
    players' materials.

    Returns:
        List of junk items.

    Raises:
        AccessDeniedException: If the user doesn't own the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.junk.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)


@router.get("/{junk_id}", response_model=JunkRead)
async def read_junk(
    junk_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Junk:
    """Retrieve a junk item by ID.

    Returns:
        The requested junk item.

    Raises:
        AccessDeniedException: If the user doesn't own the junk item's vault.
    """
    await verify_item_access(junk_id, Junk, user, db_session)
    return await crud.junk.get(db_session, junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
async def update_junk(
    junk_id: UUID4,
    junk_data: JunkUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Junk:
    """Update a junk item (administrators only).

    Returns:
        The updated junk item.
    """
    return await crud.junk.update(db_session, junk_id, junk_data)


@router.delete("/{junk_id}", status_code=204)
async def delete_junk(
    junk_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> None:
    """Delete a junk item (administrators only)."""
    await crud.junk.delete(db_session, junk_id)


@router.get("/read_data/", response_model=list[JunkCreate])
async def read_junk_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[JunkCreate]:
    """Retrieve static junk item data.

    Returns:
        List of static junk item definitions.
    """
    return data_store.junk_items


@router.post("/{junk_id}/sell/", status_code=200, response_model=None)
async def sell_junk(
    junk_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Sell a junk item for caps.

    Raises:
        AccessDeniedException: If the user doesn't own the junk item's vault.
    """
    await verify_item_access(junk_id, Junk, user, db_session)
    await item_service.sell_item(db_session, item_id=junk_id, model=Junk)
