from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate

router = APIRouter()


@router.post("/", response_model=JunkRead)
async def create_junk(junk_data: JunkCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.junk.create(db_session, junk_data)


@router.get("/", response_model=list[JunkRead])
async def read_junk_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.junk.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{junk_id}", response_model=JunkRead)
async def read_junk(junk_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.junk.get(db_session, junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
async def update_junk(junk_id: UUID4, junk_data: JunkUpdate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.junk.update(db_session, junk_id, junk_data)


@router.delete("/{junk_id}", status_code=204)
async def delete_junk(junk_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.junk.delete(db_session, junk_id)
