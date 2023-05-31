from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate

router = APIRouter()


@router.post("/", response_model=OutfitRead)
async def create_outfit(outfit_data: OutfitCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.create(db_session, outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.get(db_session, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID4,
    outfit_data: OutfitUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.outfit.update(db_session, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.delete(db_session, outfit_id)
