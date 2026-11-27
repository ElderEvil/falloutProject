"""Admin item writes own exactly one commit and roll back on a failed write."""

import pytest
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate
from app.services.item_service import item_service
from app.tests.factory.items import create_fake_weapon
from app.tests.test_services._transaction_helpers import counting_commit, fail_sql


def _inserts_weapon(statement: str) -> bool:
    return statement.lower().startswith("insert into weapon")


def _updates_weapon(statement: str) -> bool:
    return statement.lower().startswith("update weapon")


def _deletes_weapon(statement: str) -> bool:
    return statement.lower().startswith("delete from weapon")


def _weapon_create() -> WeaponCreate:
    return WeaponCreate(**create_fake_weapon())


async def test_admin_item_writes_commit_once(async_session: AsyncSession) -> None:
    commits = counting_commit(async_session)
    weapon = await item_service.create_item(async_session, model=Weapon, item_data=_weapon_create())
    assert len(commits) == 1

    updated = await item_service.update_item(
        async_session, model=Weapon, item_id=weapon.id, item_data=WeaponUpdate(name="Renamed")
    )
    assert updated.name == "Renamed"
    assert len(commits) == 2

    await item_service.delete_item(async_session, model=Weapon, item_id=weapon.id)
    assert len(commits) == 3
    assert await crud.weapon.get_or_none(async_session, weapon.id) is None


async def test_admin_item_create_rolls_back_when_the_insert_fails(async_session: AsyncSession) -> None:
    async with fail_sql(async_session, _inserts_weapon, "injected weapon insert failure"):
        with pytest.raises(RuntimeError, match="injected weapon insert failure"):
            await item_service.create_item(async_session, model=Weapon, item_data=_weapon_create())

    await async_session.rollback()
    assert (await async_session.execute(select(func.count()).select_from(Weapon))).scalar_one() == 0


async def test_admin_item_update_rolls_back_when_the_write_fails(async_session: AsyncSession) -> None:
    weapon = await crud.weapon.create(async_session, obj_in=_weapon_create())
    original_name = weapon.name

    async with fail_sql(async_session, _updates_weapon, "injected weapon update failure"):
        with pytest.raises(RuntimeError, match="injected weapon update failure"):
            await item_service.update_item(
                async_session, model=Weapon, item_id=weapon.id, item_data=WeaponUpdate(name="Never persisted")
            )

    await async_session.rollback()
    await async_session.refresh(weapon)
    assert weapon.name == original_name


async def test_admin_item_delete_rolls_back_when_the_write_fails(async_session: AsyncSession) -> None:
    weapon = await crud.weapon.create(async_session, obj_in=_weapon_create())

    async with fail_sql(async_session, _deletes_weapon, "injected weapon delete failure"):
        with pytest.raises(RuntimeError, match="injected weapon delete failure"):
            await item_service.delete_item(async_session, model=Weapon, item_id=weapon.id)

    await async_session.rollback()
    await async_session.refresh(weapon)
    assert weapon.id is not None
