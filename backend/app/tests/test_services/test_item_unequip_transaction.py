"""Unequipping an item owns one transaction boundary (real session).

The storage return and the slot clear are staged through CRUD and committed once.
"""

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.services.item_service import item_service
from app.tests.test_services._transaction_helpers import (
    counting_commit,
    fail_sql,
    fresh_session,
    record_statements,
)
from app.utils.exceptions import ResourceNotFoundException

pytestmark = pytest.mark.asyncio


def _writes_item(statement: str) -> bool:
    """The unequip's single write: the item row moves to storage and loses its dweller."""
    return statement.lower().startswith("update weapon")


async def _vault_storage(async_session: AsyncSession, vault_id: UUID) -> Storage:
    """The vault's own storage row; the unequip query joins through it."""
    storage = await storage_crud.get_by_vault(async_session, vault_id)
    if storage is None:
        storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


async def test_unequip_commits_once_and_persists_both_writes(
    async_session: AsyncSession, equipped_dweller: tuple[Dweller, object, Weapon]
) -> None:
    dweller, _, weapon = equipped_dweller
    weapon_id, dweller_id = weapon.id, dweller.id
    storage = await _vault_storage(async_session, dweller.vault_id)
    commits = counting_commit(async_session)

    await item_service.unequip_item(async_session, item_id=weapon_id, model=Weapon)

    assert len(commits) == 1, f"unequipping committed {len(commits)} times; the service owns exactly one"
    reloaded_weapon = await crud.weapon.get(async_session, weapon_id)
    assert reloaded_weapon.dweller_id is None, "the unequipped weapon must leave the dweller"
    assert reloaded_weapon.storage_id == storage.id, "the unequipped weapon must return to the vault's storage"
    reloaded_dweller = await async_session.get(Dweller, dweller_id)
    assert reloaded_dweller is not None
    assert reloaded_dweller.weapon is None, "the dweller's weapon slot must be cleared"


async def test_failure_at_the_item_write_leaves_the_item_equipped(
    async_session: AsyncSession, equipped_dweller: tuple[Dweller, object, Weapon], db_connection
) -> None:
    """The item move and the slot clear are one row update; a failed write must commit nothing."""
    dweller, _, weapon = equipped_dweller
    weapon_id, dweller_id = weapon.id, dweller.id
    await _vault_storage(async_session, dweller.vault_id)

    with pytest.raises(RuntimeError, match="injected item failure"):
        async with fail_sql(async_session, _writes_item, "injected item failure"):
            await item_service.unequip_item(async_session, item_id=weapon_id, model=Weapon)
    # A listener raising mid-flush leaves this session poisoned; read the outcome on a fresh one.
    await async_session.close()
    async with fresh_session(db_connection) as session:
        reloaded_weapon = await crud.weapon.get(session, weapon_id)
        assert reloaded_weapon.dweller_id == dweller_id, "the item must stay equipped after a failed unequip"
        reloaded_dweller = (await session.execute(select(Dweller).where(Dweller.id == dweller_id))).scalar_one()
        await session.refresh(reloaded_dweller, ["weapon"])
        assert reloaded_dweller.weapon is not None, "the dweller's slot must be unchanged by a failed unequip"


async def test_unequip_does_no_database_work_after_its_commit(
    async_session: AsyncSession, equipped_dweller: tuple[Dweller, object, Weapon]
) -> None:
    """The commit must be the last thing the operation does before returning."""
    dweller, _, weapon = equipped_dweller
    await _vault_storage(async_session, dweller.vault_id)

    async with record_statements(async_session) as (statements, commit_marks):
        await item_service.unequip_item(async_session, item_id=weapon.id, model=Weapon)

    assert len(commit_marks) == 1
    trailing = statements[commit_marks[0] :]
    assert not trailing, f"{len(trailing)} statements ran after the unequip commit: {trailing}"


async def test_repeat_unequip_raises_the_same_not_found_error(
    async_session: AsyncSession, equipped_dweller: tuple[Dweller, object, Weapon]
) -> None:
    dweller, _, weapon = equipped_dweller
    await _vault_storage(async_session, dweller.vault_id)

    await item_service.unequip_item(async_session, item_id=weapon.id, model=Weapon)
    commits = counting_commit(async_session)

    with pytest.raises(ResourceNotFoundException):
        await item_service.unequip_item(async_session, item_id=weapon.id, model=Weapon)

    assert commits == [], "a rejected repeat must not commit anything"
