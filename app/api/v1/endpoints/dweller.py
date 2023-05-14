from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel import Session

from app import crud
from app.db.base import get_session
from app.schemas.dweller import DwellerCreate, DwellerRead, DwellerUpdate

router = APIRouter()


@router.post("/", response_model=DwellerRead)
def create_dweller(dweller_data: DwellerCreate, db: Session = Depends(get_session)):
    return crud.dweller.create(db, dweller_data)


@router.get("/", response_model=list[DwellerRead])
def read_dweller_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    return crud.dweller.get_multi(db, skip=skip, limit=limit)


@router.get("/{dweller_id}", response_model=DwellerRead)
def read_dweller(dweller_id: UUID4, db: Session = Depends(get_session)):
    return crud.dweller.get(db, dweller_id)


@router.put("/{dweller_id}", response_model=DwellerRead)
def update_dweller(dweller_id: UUID4, dweller_data: DwellerUpdate, db: Session = Depends(get_session)):
    return crud.dweller.update(db, dweller_id, dweller_data)


@router.delete("/{dweller_id}", status_code=204)
def delete_dweller(dweller_id: UUID4, db: Session = Depends(get_session)):
    return crud.dweller.delete(db, dweller_id)
