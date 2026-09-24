"""CRUDItem.equip held-state and commit-optional behavior (issue #765 workstream 1).

Real-DB tests: first equip, displaced-item routing (storage vs held), commit=False
transaction ownership, error paths, and the held-for-exploration helpers.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.models.weapon import Weapon
from app.tests.factory.items import create_fake_weapon
from app.utils.exceptions import ContentNoChangeException, ResourceNotFoundException


async def _create_weapon(async_session: AsyncSession) -> Weapon:
    return await crud.weapon.create(async_session, obj_in=create_fake_weapon())


@pytest.mark.asyncio
async def test_first_equip_assigns_dweller_only(async_session: AsyncSession, dweller) -> None:
    weapon = await _create_weapon(async_session)

    equipped = await crud.weapon.equip(db_session=async_session, item_id=weapon.id, dweller_id=dweller.id)

    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


@pytest.mark.asyncio
async def test_reequip_default_returns_displaced_to_storage(async_session: AsyncSession, dweller, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await crud.weapon.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)

    await crud.weapon.equip(db_session=async_session, item_id=new.id, dweller_id=dweller.id)

    displaced = await crud.weapon.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id == storage.id
    assert displaced.exploration_id is None
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


@pytest.mark.asyncio
async def test_reequip_held_moves_displaced_to_exploration(async_session: AsyncSession, dweller) -> None:
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await crud.weapon.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    held_id = uuid4()

    await crud.weapon.equip(
        db_session=async_session, item_id=new.id, dweller_id=dweller.id, held_exploration_id=held_id
    )

    displaced = await crud.weapon.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id is None
    assert displaced.exploration_id == held_id
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    assert equipped.exploration_id is None


@pytest.mark.asyncio
async def test_equip_commit_false_does_not_commit(async_session: AsyncSession, dweller) -> None:
    weapon = await _create_weapon(async_session)

    equipped = await crud.weapon.equip(db_session=async_session, item_id=weapon.id, dweller_id=dweller.id, commit=False)

    assert equipped.dweller_id == dweller.id
    reloaded = await crud.weapon.get(async_session, weapon.id)
    assert reloaded.dweller_id == dweller.id

    weapon_id = weapon.id
    await async_session.rollback()
    result = await async_session.execute(select(Weapon).where(Weapon.id == weapon_id))
    reloaded = result.scalar_one_or_none()
    assert reloaded is not None
    assert reloaded.dweller_id is None


@pytest.mark.asyncio
async def test_equip_same_item_raises_content_no_change(async_session: AsyncSession, dweller) -> None:
    weapon = await _create_weapon(async_session)
    await crud.weapon.equip(db_session=async_session, item_id=weapon.id, dweller_id=dweller.id)

    with pytest.raises(ContentNoChangeException):
        await crud.weapon.equip(db_session=async_session, item_id=weapon.id, dweller_id=dweller.id)


@pytest.mark.asyncio
async def test_equip_missing_dweller_raises(async_session: AsyncSession) -> None:
    weapon = await _create_weapon(async_session)

    with pytest.raises(ResourceNotFoundException):
        await crud.weapon.equip(db_session=async_session, item_id=weapon.id, dweller_id=uuid4())


@pytest.mark.asyncio
async def test_equip_missing_item_raises(async_session: AsyncSession, dweller) -> None:
    with pytest.raises(ResourceNotFoundException):
        await crud.weapon.equip(db_session=async_session, item_id=uuid4(), dweller_id=dweller.id)


@pytest.mark.asyncio
async def test_get_held_for_exploration(async_session: AsyncSession, dweller) -> None:
    held_id = uuid4()
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await crud.weapon.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    await crud.weapon.equip(
        db_session=async_session, item_id=new.id, dweller_id=dweller.id, held_exploration_id=held_id
    )

    held = await crud.weapon.get_held_for_exploration(async_session, held_id)
    assert [w.id for w in held] == [old.id]
    assert await crud.weapon.get_held_for_exploration(async_session, uuid4()) == []


@pytest.mark.asyncio
async def test_delete_held_for_exploration(async_session: AsyncSession, dweller) -> None:
    held_id = uuid4()
    old = await _create_weapon(async_session)
    new = await _create_weapon(async_session)
    await crud.weapon.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    await crud.weapon.equip(
        db_session=async_session, item_id=new.id, dweller_id=dweller.id, held_exploration_id=held_id
    )

    count = await crud.weapon.delete_held_for_exploration(async_session, held_id)
    await async_session.flush()

    assert count == 1
    assert await crud.weapon.get_held_for_exploration(async_session, held_id) == []
    equipped = await crud.weapon.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
