from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel import Session

from app import crud
from app.db.base import get_session
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate

router = APIRouter()


@router.post("/", response_model=Weapon)
def create_weapon(weapon_data: WeaponCreate, db: Session = Depends(get_session)):
    return crud.weapon.create(db, weapon_data)


@router.get("/", response_model=list[Weapon])
def read_weapon_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    return crud.weapon.get_multi(db, skip=skip, limit=limit)


@router.get("/{weapon_id}", response_model=Weapon)
def read_weapon(weapon_id: UUID4, db: Session = Depends(get_session)):
    return crud.weapon.get(db, weapon_id)


@router.put("/{weapon_id}", response_model=Weapon)
def update_weapon(weapon_id: UUID4, weapon_data: WeaponUpdate, db: Session = Depends(get_session)):
    return crud.weapon.update(db, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
def delete_weapon(weapon_id: UUID4, db: Session = Depends(get_session)):
    return crud.weapon.delete(db, weapon_id)
