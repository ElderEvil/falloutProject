from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.schemas.dweller import DwellerCreate, DwellerRead, DwellerUpdate

router = APIRouter()


@router.post("/", response_model=DwellerRead)
async def create_dweller(dweller_data: DwellerCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.create(db_session, dweller_data)


@router.get("/", response_model=list[DwellerRead])
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

@router.post("/{dweller_id}/assign_room/{room_id}", response_model=DwellerRead)
async def assign_room(dweller_id: UUID4, room_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.assign_room(db_session, dweller_id, room_id)

@router.post("/{dweller_id}/equip_weapon/{weapon_id}", response_model=DwellerRead)
async def equip_weapon(dweller_id: UUID4, weapon_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.equip_weapon(db_session, dweller_id, weapon_id)

@router.post("/{dweller_id}/unequip_weapon/", response_model=DwellerRead)
async def unequip_weapon(dweller_id: UUID4, weapon_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.unequip_weapon(db_session, dweller_id, weapon_id)

@router.post("/{dweller_id}/equip_outfit/{outfit_id}", response_model=DwellerRead)
async def equip_outfit(dweller_id: UUID4, outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.equip_outfit(db_session, dweller_id, outfit_id)

@router.post("/{dweller_id}/unequip_outfit/", response_model=DwellerRead) 
async def unequip_outfit(dweller_id: UUID4, outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.dweller.unequip_outfit(db_session, dweller_id, outfit_id)