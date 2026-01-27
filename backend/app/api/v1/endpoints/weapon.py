from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.junk import JunkRead
from app.schemas.weapon import WeaponCreate, WeaponRead, WeaponUpdate

router = APIRouter()


@router.post("/", response_model=WeaponRead)
async def create_weapon(weapon_data: WeaponCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.weapon.create(db_session, weapon_data)


@router.get("/", response_model=list[WeaponRead])
async def read_weapon_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    vault_id: UUID4 | None = None,
):
    """Get weapons, optionally filtered by vault."""
    import logging

    logger = logging.getLogger(__name__)

    if vault_id:
        # Filter by vault: items in vault's storage OR equipped by vault's dwellers
        from sqlmodel import or_, select

        from app.models.dweller import Dweller
        from app.models.storage import Storage

        # Subqueries for vault's storage and dwellers
        storage_subquery = select(Storage.id).where(Storage.vault_id == vault_id).scalar_subquery()
        dweller_subquery = select(Dweller.id).where(Dweller.vault_id == vault_id).scalar_subquery()

        query = (
            select(crud.weapon.model)
            .where(
                or_(
                    crud.weapon.model.storage_id.in_(storage_subquery),
                    crud.weapon.model.dweller_id.in_(dweller_subquery),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db_session.execute(query)
        weapons = result.scalars().all()
        logger.info(f"Fetched {len(weapons)} weapons for vault {vault_id}")
        return weapons

    return await crud.weapon.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{weapon_id}", response_model=WeaponRead)
async def read_weapon(weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.weapon.get(db_session, weapon_id)


@router.put("/{weapon_id}", response_model=WeaponRead)
async def update_weapon(
    weapon_id: UUID4,
    weapon_data: WeaponUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.weapon.update(db_session, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
async def delete_weapon(weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.weapon.delete(db_session, weapon_id)


@router.post("/{dweller_id}/equip/{weapon_id}", response_model=WeaponRead)
async def equip_weapon(
    dweller_id: UUID4, weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.weapon.equip(db_session=db_session, item_id=weapon_id, dweller_id=dweller_id)


@router.post("/{weapon_id}/unequip/", status_code=200)
async def unequip_weapon(weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.weapon.unequip(db_session=db_session, item_id=weapon_id)


@router.post("/{weapon_id}/scrap/", response_model=dict[str, list[JunkRead]] | None)
async def scrap_weapon(weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    junk_list = await crud.weapon.scrap(db_session=db_session, item_id=weapon_id)
    return {"junk": junk_list}


@router.post("/{weapon_id}/sell/", status_code=200)
async def sell_weapon(weapon_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.weapon.sell(db_session=db_session, item_id=weapon_id)


@router.get("/read_data/", response_model=list[WeaponCreate])
async def read_weapons_data(data_store=Depends(get_static_game_data)):
    return data_store.weapons
