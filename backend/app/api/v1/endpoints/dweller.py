from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerCreateWithoutVaultID,
    DwellerRead,
    DwellerReadFull,
    DwellerReadLess,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.services.dweller_ai import dweller_ai

router = APIRouter()


@router.post("/", response_model=DwellerRead)
async def create_dweller(dweller_data: DwellerCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.create(db_session, dweller_data)


@router.get("/", response_model=list[DwellerReadLess])
async def read_dweller_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.get_multi(db_session=db_session, skip=skip, limit=limit)


@router.get("/{dweller_id}", response_model=DwellerRead)
async def read_dweller(dweller_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.get(db_session, dweller_id)


@router.put("/{dweller_id}", response_model=DwellerRead)
async def update_dweller(
    dweller_id: UUID4,
    dweller_data: DwellerUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.dweller.update(db_session, dweller_id, dweller_data)


@router.delete("/{dweller_id}", status_code=204)
async def delete_dweller(dweller_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.delete(db_session, dweller_id)


@router.post("/{dweller_id}/move_to/{room_id}", response_model=DwellerReadWithRoomID)
async def move_dweller_to_room(
    dweller_id: UUID4,
    room_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.dweller.move_to_room(db_session, dweller_id, room_id)


@router.post("/create_random/", response_model=DwellerRead)
async def create_random_common_dweller(
    vault_id: UUID4,
    dweller_override: DwellerCreateCommonOverride | None = None,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.dweller.create_random(db_session=db_session, obj_in=dweller_override, vault_id=vault_id)


@router.post("/{dweller_id}/generate_backstory/", response_model=DwellerReadFull)
async def generate_backstory(
    dweller_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await dweller_ai.generate_backstory(db_session=db_session, dweller_id=dweller_id)


@router.post("/{dweller_id}/generate_visual_attributes/", response_model=DwellerReadFull)
async def generate_visual_attributes(
    dweller_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await dweller_ai.generate_visual_attributes(db_session=db_session, dweller_id=dweller_id)


@router.post("/{dweller_id}/generate_photo/", response_model=DwellerReadFull)
async def generate_photo(
    dweller_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await dweller_ai.generate_photo(db_session=db_session, dweller_id=dweller_id)


@router.post("/{dweller_id}/generate_with_ai/", response_model=DwellerReadFull)
async def generate_data_with_ai(
    dweller_id: UUID4,
    origin: str | None = None,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await dweller_ai.dweller_generate_pipeline(db_session=db_session, dweller_id=dweller_id, origin=origin)


@router.get("/read_data/", response_model=list[DwellerCreateWithoutVaultID])
async def read_dwellers_data(data_store=Depends(get_static_game_data)):
    return data_store.dwellers
