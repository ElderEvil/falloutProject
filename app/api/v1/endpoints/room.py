from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate, RoomCreateWithoutVaultID

router = APIRouter()


@router.post("/", response_model=RoomRead)
async def create_room(room_data: RoomCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.create(db_session=db_session, obj_in=room_data)


@router.get("/", response_model=list[RoomRead])
async def read_room_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{room_id}", response_model=RoomRead)
async def read_room(room_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.get(db_session, room_id)


@router.put("/{room_id}", response_model=RoomRead)
async def update_room(room_id: UUID4, room_data: RoomUpdate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.update(db_session, room_id, room_data)


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.delete(db_session, room_id)


@router.get("/read_data/", response_model=list[RoomCreateWithoutVaultID])
async def read_room_data(data_store=Depends(get_static_game_data)):
    return data_store.rooms


@router.post("/build/", response_model=RoomRead)
async def build_room(room_data: RoomCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.room.build(db_session=db_session, obj_in=room_data)
