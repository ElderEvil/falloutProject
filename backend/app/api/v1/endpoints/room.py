"""Room endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_room_access
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.room import RoomBuild, RoomCreateWithoutVaultID, RoomRead
from app.services.room_service import room_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/rooms", tags=["Room"])


@router.get("/", response_model=list[RoomRead])
async def read_room_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)], skip: int = 0, limit: int = 100
) -> list[RoomRead]:
    """Retrieve a paginated list of rooms.

    Returns:
        List of rooms.
    """
    return await crud.room.get_multi(db_session, skip=skip, limit=limit)


@router.get("/vault/{vault_id}/", response_model=list[RoomRead])
async def read_rooms_by_vault(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> list[RoomRead]:
    """Retrieve rooms for a specific vault.

    Returns:
        List of rooms in the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.room.get_multy_by_vault(db_session=db_session, skip=skip, limit=limit, vault_id=vault_id)


@router.get("/{room_id}", response_model=RoomRead)
async def read_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> RoomRead:
    """Retrieve a room by ID.

    Returns:
        The requested room.
    """
    await verify_room_access(room_id, user, db_session)
    return await crud.room.get(db_session, room_id)


@router.get("/read_data/", response_model=list[RoomCreateWithoutVaultID])
async def read_room_data(
    data_store: Annotated[StaticGameData, Depends(get_static_game_data)],
) -> list[RoomCreateWithoutVaultID]:
    """Retrieve static room data definitions.

    Returns:
        List of static room definitions.
    """
    return data_store.rooms


@router.get("/buildable/{vault_id}/", response_model=list[RoomCreateWithoutVaultID])
async def get_buildable_rooms(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[RoomCreateWithoutVaultID]:
    """Get list of rooms that can be built in a vault.

    Filters out:
    - Vault door (never buildable by user)
    - Unique rooms that are already built in this vault

    Returns:
        List of buildable room definitions.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await room_service.get_buildable_rooms(db_session, vault_id)


@router.post("/build/", response_model=RoomRead)
async def build_room(
    room_request: RoomBuild,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RoomRead:
    """Build a new room in a vault.

    Returns:
        The built room.
    """
    await get_user_vault_or_403(room_request.vault_id, user, db_session)
    return await room_service.build_room(db_session, room_request)


@router.delete("/destroy/{room_id}", status_code=204)
async def destroy_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Destroy a room in a vault."""
    await verify_room_access(room_id, user, db_session)
    return await room_service.destroy_room(db_session, room_id)


@router.post("/upgrade/{room_id}", response_model=RoomRead)
async def upgrade_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RoomRead:
    """Upgrade a room to the next level.

    Returns:
        The upgraded room.
    """
    await verify_room_access(room_id, user, db_session)
    return await room_service.upgrade_room(db_session, room_id)
