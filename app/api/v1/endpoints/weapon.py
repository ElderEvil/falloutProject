from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.schemas.weapon import WeaponCreate, WeaponRead, WeaponUpdate

router = APIRouter()


@router.post("/", response_model=WeaponRead)
async def create_weapon(weapon_data: WeaponCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.create(db_session, weapon_data)


@router.get("/", response_model=list[WeaponRead])
async def read_weapon_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{weapon_id}", response_model=WeaponRead)
async def read_weapon(weapon_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.get(db_session, weapon_id)


@router.put("/{weapon_id}", response_model=WeaponRead)
async def update_weapon(
    weapon_id: UUID4,
    weapon_data: WeaponUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.weapon.update(db_session, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
async def delete_weapon(weapon_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.weapon.delete(db_session, weapon_id)
