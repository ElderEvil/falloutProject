from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403, verify_dweller_access
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.common import DwellerStatusEnum
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerCreateWithoutVaultID,
    DwellerRead,
    DwellerReadFull,
    DwellerReadLess,
    DwellerReadWithRoomID,
    DwellerUpdate,
    DwellerVisualAttributesInput,
)
from app.services.dweller_ai import dweller_ai

router = APIRouter()


@router.post("/", response_model=DwellerRead)
async def create_dweller(
    dweller_data: DwellerCreate,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.dweller.create(db_session, dweller_data)


@router.get("/", response_model=list[DwellerReadLess])
async def read_dweller_list(
    # vault_id: UUID4,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    return await crud.dweller.get_multi(db_session=db_session, skip=skip, limit=limit)


@router.get("/{dweller_id}", response_model=DwellerReadFull)
async def read_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.get(db_session, dweller_id)


@router.put("/{dweller_id}", response_model=DwellerRead)
async def update_dweller(
    dweller_id: UUID4,
    dweller_data: DwellerUpdate,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    # If room_id is being updated, automatically update status
    if dweller_data.room_id is not None or (
        hasattr(dweller_data, "model_fields_set") and "room_id" in dweller_data.model_fields_set
    ):
        from app.schemas.common import DwellerStatusEnum, RoomTypeEnum

        if dweller_data.room_id is None:
            # Unassigning from room - set to IDLE
            dweller_data.status = DwellerStatusEnum.IDLE
        else:
            # Assigning to room - set status based on room type
            room_obj = await crud.room.get(db_session, dweller_data.room_id)
            if room_obj.category == RoomTypeEnum.TRAINING:
                dweller_data.status = DwellerStatusEnum.TRAINING
            elif room_obj.category == RoomTypeEnum.PRODUCTION:
                dweller_data.status = DwellerStatusEnum.WORKING
            else:
                dweller_data.status = DwellerStatusEnum.WORKING

    return await crud.dweller.update(db_session, dweller_id, dweller_data)


@router.delete("/{dweller_id}", status_code=204)
async def delete_dweller(
    dweller_id: UUID4, _: CurrentSuperuser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.dweller.delete(db_session, dweller_id)


@router.get("/vault/{vault_id}/", response_model=list[DwellerReadLess])
async def read_dwellers_by_vault(  # noqa: PLR0913
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    status: DwellerStatusEnum | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
):
    """Get dwellers by vault with optional filtering by status, search by name, and sorting."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.get_multi_by_vault(
        db_session=db_session,
        vault_id=vault_id,
        skip=skip,
        limit=limit,
        status=status,
        search=search,
        sort_by=sort_by,
        order=order,
    )


@router.post("/{dweller_id}/move_to/{room_id}", response_model=DwellerReadWithRoomID)
async def move_dweller_to_room(
    dweller_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.move_to_room(db_session, dweller_id, room_id)


@router.post("/create_random/", response_model=DwellerRead)
async def create_random_common_dweller(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_override: DwellerCreateCommonOverride | None = None,
):
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.create_random(db_session=db_session, obj_in=dweller_override, vault_id=vault_id)


@router.post("/{dweller_id}/generate_backstory/", response_model=DwellerReadFull)
async def generate_backstory(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_backstory(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_visual_attributes/", response_model=DwellerReadFull)
async def generate_visual_attributes(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_visual_attributes(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_photo/", response_model=DwellerReadFull)
async def generate_photo(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_photo(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_audio/", response_model=DwellerReadFull)
async def generate_audio(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    text: str | None = None,
):
    return await dweller_ai.generate_audio(db_session=db_session, dweller_id=dweller_id, user=user, text=text)


@router.post("/{dweller_id}/generate_with_ai/", response_model=DwellerReadFull)
async def generate_data_with_ai(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    origin: str | None = None,
):
    return await dweller_ai.dweller_generate_pipeline(
        db_session=db_session, dweller_id=dweller_id, origin=origin, user=user
    )


@router.post("/{dweller_id}/generate_avatar", response_model=DwellerReadFull)
async def generate_dweller_avatar(  # noqa: PLR0913
    dweller_id: UUID4,
    dweller_first_name: str,
    dweller_last_name: str,
    visual_attributes_input: DwellerVisualAttributesInput,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
):
    return await dweller_ai.generate_dweller_avatar(
        db_session=db_session,
        dweller_id=dweller_id,
        dweller_first_name=dweller_first_name,
        dweller_last_name=dweller_last_name,
        visual_attributes_input=visual_attributes_input,
        user=current_user,
    )


@router.get("/read_data/", response_model=list[DwellerCreateWithoutVaultID])
def read_dwellers_data(data_store=Depends(get_static_game_data)):
    return data_store.dwellers
