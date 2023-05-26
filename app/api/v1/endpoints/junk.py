from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.base import get_async_session
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate

router = APIRouter()


@router.post("/", response_model=JunkRead)
async def create_junk(junk_data: JunkCreate, db: AsyncSession = Depends(get_async_session)):
    return await crud.junk.create(db, junk_data)


@router.get("/", response_model=list[JunkRead])
async def read_junk_list(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    return await crud.junk.get_multi(db, skip=skip, limit=limit)


@router.get("/{junk_id}", response_model=JunkRead)
async def read_junk(junk_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.junk.get(db, junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
async def update_junk(junk_id: UUID4, junk_data: JunkUpdate, db: AsyncSession = Depends(get_async_session)):
    return await crud.junk.update(db, junk_id, junk_data)


@router.delete("/{junk_id}", status_code=204)
async def delete_junk(junk_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.junk.delete(db, junk_id)
