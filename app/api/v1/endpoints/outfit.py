from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.crud.outfit import outfit
from app.db.base import get_session
from app.schemas.outfit import OutfitRead, OutfitCreate, OutfitUpdate

router = APIRouter()


@router.post("/", response_model=OutfitRead)
def create_outfit(outfit_data: OutfitCreate, db: Session = Depends(get_session)):
    return outfit.create(db, outfit_data)


@router.get("/", response_model=list[OutfitRead])
def read_outfit_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    outfit_items = outfit.get_multi(db, skip=skip, limit=limit)
    return outfit_items


@router.get("/{outfit_id}", response_model=OutfitRead)
def read_outfit(outfit_id: int, db: Session = Depends(get_session)):
    return outfit.get(db, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
def update_outfit(outfit_id: int, outfit_data: OutfitUpdate, db: Session = Depends(get_session)):
    return outfit.update(db, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
def delete_outfit(outfit_id: int, db: Session = Depends(get_session)):
    return outfit.delete(db, outfit_id)
