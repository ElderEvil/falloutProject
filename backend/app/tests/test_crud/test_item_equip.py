from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.models.weapon import Weapon
from app.services.exploration_service import exploration_service
from app.tests.factory.items import create_fake_weapon
from app.utils.exceptions import ContentNoChangeException, ResourceNotFoundException


async def _create_weapon(async_session: AsyncSession) -> Weapon:
    return await crud.weapon.create(async_session, obj_in=create_fake_weapon())


async def _equip(async_session: AsyncSession, item, dweller, **kw):
    return await crud.weapon.equip(db_session=async_session, item_id=item.id, dweller_id=dweller.id, **kw)


async def _held_pair(async_session: AsyncSession, vault, dweller):
    """Equip an old weapon, send the dweller exploring, then displace it into the held slot."""
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await _equip(async_session, old, dweller)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    held_id = exploration.id
    await _equip(async_session, new, dweller, held_exploration_id=held_id)
    return held_id, old, new


async def test_first_equip_assigns_dweller_only(async_session: AsyncSession, dweller) -> None:
    weapon = await _create_weapon(async_session)
    equipped = await _equip(async_session, weapon, dweller)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


async def test_reequip_default_returns_displaced_to_storage(async_session: AsyncSession, dweller, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await _equip(async_session, old, dweller)
    await _equip(async_session, new, dweller)
    displaced = await crud.weapon.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id == storage.id
    assert displaced.exploration_id is None
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


async def test_reequip_held_moves_displaced_to_exploration(async_session: AsyncSession, dweller, vault) -> None:
    held_id, old, new = await _held_pair(async_session, vault, dweller)
    displaced = await crud.weapon.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id is None
    assert displaced.exploration_id == held_id
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


async def test_equip_commit_false_does_not_commit(async_session: AsyncSession, dweller) -> None:
    weapon = await _create_weapon(async_session)
    equipped = await _equip(async_session, weapon, dweller, commit=False)
    assert equipped.dweller_id == dweller.id
    reloaded = await crud.weapon.get(async_session, weapon.id)
    assert reloaded.dweller_id == dweller.id
    weapon_id = weapon.id
    await async_session.rollback()
    result = await async_session.execute(select(Weapon).where(Weapon.id == weapon_id))
    reloaded = result.scalar_one_or_none()
    assert reloaded is not None
    assert reloaded.dweller_id is None


@pytest.mark.parametrize("case", ["same_item", "missing_dweller", "missing_item"])
async def test_equip_errors(async_session: AsyncSession, dweller, case) -> None:
    weapon = await _create_weapon(async_session)
    if case == "same_item":
        await _equip(async_session, weapon, dweller)
        with pytest.raises(ContentNoChangeException):
            await _equip(async_session, weapon, dweller)
        return
    item_id, dweller_id = (weapon.id, uuid4()) if case == "missing_dweller" else (uuid4(), dweller.id)
    with pytest.raises(ResourceNotFoundException):
        await crud.weapon.equip(db_session=async_session, item_id=item_id, dweller_id=dweller_id)


async def test_get_held_for_exploration(async_session: AsyncSession, dweller, vault) -> None:
    held_id, old, _new = await _held_pair(async_session, vault, dweller)
    held = await crud.weapon.get_held_for_exploration(async_session, held_id)
    assert [w.id for w in held] == [old.id]
    assert await crud.weapon.get_held_for_exploration(async_session, uuid4()) == []


async def test_delete_held_for_exploration(async_session: AsyncSession, dweller, vault) -> None:
    held_id, _old, new = await _held_pair(async_session, vault, dweller)
    count = await crud.weapon.delete_held_for_exploration(async_session, held_id)
    await async_session.flush()
    assert count == 1
    assert await crud.weapon.get_held_for_exploration(async_session, held_id) == []
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
