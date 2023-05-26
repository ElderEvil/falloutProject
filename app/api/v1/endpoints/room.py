from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.base import get_async_session
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate

router = APIRouter()


@router.post("/", response_model=RoomRead)
async def create_room(room_data: RoomCreate, db: AsyncSession = Depends(get_async_session)):
    return await crud.room.create(db, room_data)


@router.get("/", response_model=list[RoomRead])
async def read_room_list(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    return await crud.room.get_multi(db, skip=skip, limit=limit)


@router.get("/{room_id}", response_model=RoomRead)
async def read_room(room_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.room.get(db, room_id)


@router.put("/{room_id}", response_model=RoomRead)
async def update_room(room_id: UUID4, room_data: RoomUpdate, db: AsyncSession = Depends(get_async_session)):
    return await crud.room.update(db, room_id, room_data)


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.room.delete(db, room_id)
