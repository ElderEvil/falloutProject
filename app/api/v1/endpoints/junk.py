from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.crud.junk import junk
from app.db.base import get_session
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate

router = APIRouter()


@router.post("/", response_model=JunkRead)
def create_junk(junk_data: JunkCreate, db: Session = Depends(get_session)):
    return junk.create(db, junk_data)


@router.get("/", response_model=list[JunkRead])
def read_junk_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    junk_items = junk.get_multi(db, skip=skip, limit=limit)
    return junk_items  # noqa: RET504


@router.get("/{junk_id}", response_model=JunkRead)
def read_junk(junk_id: int, db: Session = Depends(get_session)):
    return junk.get(db, junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
def update_junk(junk_id: int, junk_data: JunkUpdate, db: Session = Depends(get_session)):
    return junk.update(db, junk_id, junk_data)


@router.delete("/{junk_id}", status_code=204)
def delete_junk(junk_id: int, db: Session = Depends(get_session)):
    return junk.delete(db, junk_id)
