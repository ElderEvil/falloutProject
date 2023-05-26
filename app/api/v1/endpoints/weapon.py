from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.base import get_async_session
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate

router = APIRouter()


@router.post("/", response_model=Weapon)
async def create_weapon(weapon_data: WeaponCreate, db: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.create(db, weapon_data)


@router.get("/", response_model=list[Weapon])
async def read_weapon_list(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.get_multi(db, skip=skip, limit=limit)


@router.get("/{weapon_id}", response_model=Weapon)
async def read_weapon(weapon_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.get(db, weapon_id)


@router.put("/{weapon_id}", response_model=Weapon)
async def update_weapon(weapon_id: UUID4, weapon_data: WeaponUpdate, db: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.update(db, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
async def delete_weapon(weapon_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.delete(db, weapon_id)
