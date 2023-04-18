from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.models.junk import JunkCreate, JunkUpdate, Junk
from app.api.crud.junk import junk
from app.db.base import get_session

router = APIRouter()


@router.post("/junk/", response_model=Junk)
def create_junk(junk_data: JunkCreate, db: Session = Depends(get_session)):
    return junk.create(db, junk_data)


@router.get("/junk/{junk_id}", response_model=Junk)
def read_junk(junk_id: int, db: Session = Depends(get_session)):
    return junk.get(db, junk_id)


@router.get("/junk/", response_model=list[Junk])
def read_junk_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    junk_items = junk.get_multi(db, skip=skip, limit=limit)
    return junk_items


@router.put("/junk/{junk_id}", response_model=Junk)
def update_junk(junk_id: int, junk_data: JunkUpdate, db: Session = Depends(get_session)):
    return junk.update(db, junk_id, junk_data)


@router.delete("/junk/{junk_id}", response_model=Junk)
def delete_junk(junk_id: int, db: Session = Depends(get_session)):
    return junk.delete(db, junk_id)
