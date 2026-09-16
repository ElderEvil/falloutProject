"""Weapon item CRUD endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import (
    CurrentActiveUser,
    CurrentSuperuser,
    get_current_active_user,
    get_user_vault_or_403,
    verify_dweller_access,
    verify_item_access,
)
from app.core.game_data import get_static_game_data
from app.crud.item_base import get_items_list
from app.db.session import get_async_session
from app.models.weapon import Weapon
from app.schemas.responses import JunkListResponse
from app.schemas.weapon import WeaponCreate, WeaponRead, WeaponUpdate
from app.services.item_service import item_service
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/weapons", tags=["Weapon"], dependencies=[Depends(get_current_active_user)])


@router.post("/", response_model=WeaponRead)
async def create_weapon(
    weapon_data: WeaponCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Weapon:
    """Create a new weapon (administrators only).

    Returns:
        The created weapon.
    """
    return await crud.weapon.create(db_session, weapon_data)


@router.get("/", response_model=list[WeaponRead])
async def read_weapon_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
    vault_id: UUID4 | None = None,
) -> Sequence[Weapon]:
    """Retrieve a paginated list of weapons, optionally filtered by vault.

    Returns:
        List of weapons.

    Raises:
        AccessDeniedException: If a vault filter is given and the user doesn't own it.
    """
    if vault_id is not None:
        await get_user_vault_or_403(vault_id, user, db_session)
    return await get_items_list(crud.weapon, db_session, Weapon, vault_id, skip, limit)


@router.get("/{weapon_id}", response_model=WeaponRead)
async def read_weapon(
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Weapon:
    """Retrieve a weapon by ID.

    Returns:
        The requested weapon.

    Raises:
        AccessDeniedException: If the user doesn't own the weapon's vault.
    """
    await verify_item_access(weapon_id, Weapon, user, db_session)
    return await crud.weapon.get(db_session, weapon_id)


@router.put("/{weapon_id}", response_model=WeaponRead)
async def update_weapon(
    weapon_id: UUID4,
    weapon_data: WeaponUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Weapon:
    """Update a weapon (administrators only).

    Returns:
        The updated weapon.
    """
    return await crud.weapon.update(db_session, weapon_id, weapon_data)


@router.delete("/{weapon_id}", status_code=204)
async def delete_weapon(
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> None:
    """Delete a weapon (administrators only)."""
    await crud.weapon.delete(db_session, weapon_id)


@router.post("/{dweller_id}/equip/{weapon_id}", response_model=WeaponRead)
async def equip_weapon(
    dweller_id: UUID4,
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Weapon:
    """Equip a weapon on a dweller.

    Returns:
        The equipped weapon.

    Raises:
        AccessDeniedException: If the user owns neither the dweller nor the weapon.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    await verify_item_access(weapon_id, Weapon, user, db_session)
    return await crud.weapon.equip(db_session=db_session, item_id=weapon_id, dweller_id=dweller_id)


@router.post("/{weapon_id}/unequip/", status_code=200, response_model=None)
async def unequip_weapon(
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Unequip a weapon from a dweller.

    Raises:
        AccessDeniedException: If the user doesn't own the weapon's vault.
    """
    await verify_item_access(weapon_id, Weapon, user, db_session)
    await crud.weapon.unequip(db_session=db_session, item_id=weapon_id)


@router.post("/{weapon_id}/scrap/", response_model=JunkListResponse)
async def scrap_weapon(
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> JunkListResponse:
    """Scrap a weapon into junk items.

    Returns:
        List of junk items produced from scrapping.

    Raises:
        AccessDeniedException: If the user doesn't own the weapon's vault.
    """
    await verify_item_access(weapon_id, Weapon, user, db_session)
    junk_list = await crud.weapon.scrap(db_session=db_session, item_id=weapon_id)
    return JunkListResponse(junk=junk_list)


@router.post("/{weapon_id}/sell/", status_code=200, response_model=None)
async def sell_weapon(
    weapon_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Sell a weapon for caps.

    Raises:
        AccessDeniedException: If the user doesn't own the weapon's vault.
    """
    await verify_item_access(weapon_id, Weapon, user, db_session)
    await item_service.sell_item(db_session, item_id=weapon_id, model=Weapon)


@router.get("/read_data/", response_model=list[WeaponCreate])
async def read_weapons_data(data_store: Annotated[StaticGameData, Depends(get_static_game_data)]) -> list[WeaponCreate]:
    """Retrieve static weapon data definitions.

    Returns:
        List of static weapon definitions.
    """
    return data_store.weapons
