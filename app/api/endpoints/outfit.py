from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.models.outfit import Outfit, OutfitCreate, OutfitUpdate
from app.crud.outfit import outfit
from app.db.base import get_session

router = APIRouter()


@router.post("/outfit/", response_model=Outfit)
def create_outfit(outfit_data: OutfitCreate, db: Session = Depends(get_session)):
    return outfit.create(db, outfit_data)


@router.get("/outfit/{outfit_id}", response_model=Outfit)
def read_outfit(outfit_id: int, db: Session = Depends(get_session)):
    return outfit.get(db, outfit_id)


@router.get("/outfit/", response_model=list[Outfit])
def read_outfit_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    outfit_items = outfit.get_multi(db, skip=skip, limit=limit)
    return outfit_items


@router.put("/outfit/{outfit_id}", response_model=Outfit)
def update_outfit(outfit_id: int, outfit_data: OutfitUpdate, db: Session = Depends(get_session)):
    return outfit.update(db, outfit_id, outfit_data)


@router.delete("/outfit/{outfit_id}", status_code=204)
def delete_outfit(outfit_id: int, db: Session = Depends(get_session)):
    return outfit.delete(db, outfit_id)
