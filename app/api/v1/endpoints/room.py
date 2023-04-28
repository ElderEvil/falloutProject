from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.schemas.room import RoomRead, RoomCreate, RoomUpdate
from app.crud.room import room
from app.db.base import get_session

router = APIRouter()


@router.post("/", response_model=RoomRead)
def create_room(room_data: RoomCreate, db: Session = Depends(get_session)):
    return room.create(db, room_data)


@router.get("/", response_model=list[RoomRead])
def read_room_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    room_items = room.get_multi(db, skip=skip, limit=limit)
    return room_items


@router.get("/{room_id}", response_model=RoomRead)
def read_room(room_id: int, db: Session = Depends(get_session)):
    return room.get(db, room_id)


@router.put("/{room_id}", response_model=RoomRead)
def update_room(room_id: int, room_data: RoomUpdate, db: Session = Depends(get_session)):
    return room.update(db, room_id, room_data)


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: int, db: Session = Depends(get_session)):
    return room.delete(db, room_id)
