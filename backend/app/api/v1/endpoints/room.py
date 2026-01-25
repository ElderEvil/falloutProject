from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_room_access
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.room import RoomCreate, RoomCreateWithoutVaultID, RoomRead, RoomUpdate

router = APIRouter()


@router.post("/", response_model=RoomRead)
async def create_room(room_data: RoomCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.room.create(db_session=db_session, obj_in=room_data)


@router.get("/", response_model=list[RoomRead])
async def read_room_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)], skip: int = 0, limit: int = 100
):
    return await crud.room.get_multi(db_session, skip=skip, limit=limit)


@router.get("/vault/{vault_id}/", response_model=list[RoomRead])
async def read_rooms_by_vault(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
):
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.room.get_multy_by_vault(db_session=db_session, skip=skip, limit=limit, vault_id=vault_id)


@router.get("/{room_id}", response_model=RoomRead)
async def read_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    await verify_room_access(room_id, user, db_session)
    return await crud.room.get(db_session, room_id)


@router.put("/{room_id}", response_model=RoomRead)
async def update_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    room_data: RoomUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_room_access(room_id, user, db_session)
    return await crud.room.update(db_session, room_id, room_data)


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    await verify_room_access(room_id, user, db_session)
    return await crud.room.delete(db_session, room_id)


@router.get("/read_data/", response_model=list[RoomCreateWithoutVaultID])
async def read_room_data(data_store=Depends(get_static_game_data)):
    return data_store.rooms


@router.get("/buildable/{vault_id}/", response_model=list[RoomCreateWithoutVaultID])
async def get_buildable_rooms(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    data_store=Depends(get_static_game_data),
):
    """
    Get list of rooms that can be built in a vault.

    Filters out:
    - Vault door (never buildable by user)
    - Unique rooms that are already built in this vault
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    existing_room_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault_id)
    return data_store.get_buildable_rooms(existing_room_names)


@router.post("/build/", response_model=RoomRead)
async def build_room(
    room_data: RoomCreate, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    from fastapi import HTTPException

    from app.utils.exceptions import (
        InsufficientResourcesException,
        NoSpaceAvailableException,
        UniqueRoomViolationException,
    )

    await get_user_vault_or_403(room_data.vault_id, user, db_session)

    try:
        return await crud.room.build(db_session=db_session, obj_in=room_data)
    except (ValueError, InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException) as e:
        # Re-raise HTTP exceptions as-is
        if isinstance(e, (InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException)):
            raise
        # Convert ValueError to proper 400 error
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904


@router.delete("/destroy/{room_id}", status_code=204)
async def destroy_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    from fastapi import HTTPException

    await verify_room_access(room_id, user, db_session)

    try:
        return await crud.room.destroy(db_session, room_id)
    except ValueError as e:
        # Convert ValueError to proper 400 error (e.g., vault door/elevator protection)
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904


@router.post("/upgrade/{room_id}", response_model=RoomRead)
async def upgrade_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    from fastapi import HTTPException

    from app.utils.exceptions import InsufficientResourcesException

    await verify_room_access(room_id, user, db_session)
    try:
        return await crud.room.upgrade(db_session=db_session, room_id=room_id)
    except (ValueError, InsufficientResourcesException) as e:
        if isinstance(e, InsufficientResourcesException):
            raise  # Re-raise HTTPException as-is
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904
