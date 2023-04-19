from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.crud.weapon import weapon
from app.api.models.weapon import WeaponCreate, WeaponUpdate, Weapon
from app.db.base import get_session

router = APIRouter()


@router.post("/weapon/", response_model=Weapon)
def create_weapon(weapon_data: WeaponCreate, db: Session = Depends(get_session)):
    return weapon.create(db, weapon_data)


@router.get("/weapon/{weapon_id}", response_model=Weapon)
def read_weapon(weapon_id: int, db: Session = Depends(get_session)):
    return weapon.get(db, weapon_id)


@router.get("/weapon/", response_model=list[Weapon])
def read_weapon_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    weapon_items = weapon.get_multi(db, skip=skip, limit=limit)
    return weapon_items


@router.put("/weapon/{weapon_id}", response_model=Weapon)
def update_weapon(weapon_id: int, weapon_data: WeaponUpdate, db: Session = Depends(get_session)):
    return weapon.update(db, weapon_id, weapon_data)


@router.delete("/weapon/{weapon_id}", response_model=Weapon)
def delete_weapon(weapon_id: int, db: Session = Depends(get_session)):
    return weapon.delete(db, weapon_id)
