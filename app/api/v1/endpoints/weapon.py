from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.crud.weapon import weapon
from app.db.base import get_session
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate

router = APIRouter()


@router.post("/", response_model=Weapon)
def create_weapon(weapon_data: WeaponCreate, db: Session = Depends(get_session)):
    return weapon.create(db, weapon_data)


@router.get("/", response_model=list[Weapon])
def read_weapon_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    weapon_items = weapon.get_multi(db, skip=skip, limit=limit)
    return weapon_items


@router.get("/{weapon_id}", response_model=Weapon)
def read_weapon(weapon_id: int, db: Session = Depends(get_session)):
    return weapon.get(db, weapon_id)


@router.put("/{weapon_id}", response_model=Weapon)
def update_weapon(weapon_id: int, weapon_data: WeaponUpdate, db: Session = Depends(get_session)):
    return weapon.update(db, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
def delete_weapon(weapon_id: int, db: Session = Depends(get_session)):
    return weapon.delete(db, weapon_id)
