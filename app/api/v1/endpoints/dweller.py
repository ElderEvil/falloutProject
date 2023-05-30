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
