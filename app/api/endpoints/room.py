from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.models.room import Room, RoomCreate, RoomUpdate
from app.api.crud.room import room
from app.db.base import get_session

router = APIRouter()


@router.post("/room/", response_model=Room)
def create_room(room_data: RoomCreate, db: Session = Depends(get_session)):
    return room.create(db, room_data)


@router.get("/room/{room_id}", response_model=Room)
def read_room(room_id: int, db: Session = Depends(get_session)):
    return room.get(db, room_id)


@router.get("/room/", response_model=list[Room])
def read_room_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    room_items = room.get_multi(db, skip=skip, limit=limit)
    return room_items


@router.put("/room/{room_id}", response_model=Room)
def update_room(room_id: int, room_data: RoomUpdate, db: Session = Depends(get_session)):
    return room.update(db, room_id, room_data)


@router.delete("/room/{room_id}", status_code=204)
def delete_room(room_id: int, db: Session = Depends(get_session)):
    return room.delete(db, room_id)
