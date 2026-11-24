"""Scrapping an item owns one transaction boundary (real session).

Every row is staged, committed once, and only then does ``ITEM_SCRAPPED`` reach its
subscriber, which records recipe progress on its own session.
"""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RarityEnum
from app.core.event_bus import GameEvent
from app.crud.storage import storage as storage_crud
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.item_service import item_service
from app.tests.factory.items import create_fake_weapon
from app.tests.test_services._transaction_helpers import (
    counting_commit,
    fail_sql,
    fresh_session,
    record_statements,
)
from app.utils.exceptions import ResourceNotFoundException
from app.utils.item_factory import build_weapon

pytestmark = pytest.mark.asyncio


def _deletes_item(statement: str) -> bool:
    """The item delete is the last write of the staged scrap, after its junk inserts."""
    return statement.lower().startswith("delete from weapon")


async def _storage(async_session: AsyncSession, vault: Vault, *, max_space: int = 10) -> Storage:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = max_space
    async_session.add(storage)
    await async_session.commit()
    return storage


async def _weapon(async_session: AsyncSession, storage_id: UUID, rarity: RarityEnum = RarityEnum.COMMON) -> Weapon:
    weapon = build_weapon(create_fake_weapon(), rarity, storage_id=storage_id)
    return await crud.weapon.create(db_session=async_session, obj_in=weapon)


async def _junk_rows(async_session: AsyncSession, storage_id: UUID) -> list[Junk]:
    result = await async_session.execute(select(Junk).where(Junk.storage_id == storage_id))
    return list(result.scalars().all())


async def test_scrap_commits_once_and_persists_every_row(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id)
    commits = counting_commit(async_session)

    with patch("app.core.event_bus.event_bus.emit", new=AsyncMock()) as emit:
        junk_list = await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)

    assert len(commits) == 1, f"scrapping committed {len(commits)} times; the service owns exactly one"
    assert await crud.weapon.get_or_none(async_session, weapon.id) is None, "the scrapped item must be gone"
    persisted = await _junk_rows(async_session, storage.id)
    assert len(persisted) == len(junk_list) >= 1
    assert {row.id for row in persisted} == {row.id for row in junk_list}
    info = await storage_crud.get_info(async_session, storage.id)
    assert info["used_space"] == len(persisted), "the storage count must match the junk the scrap produced"
    emit.assert_awaited_once()
    assert emit.await_args.args[0] is GameEvent.ITEM_SCRAPPED


async def test_failure_at_a_later_write_leaves_the_item_and_no_junk(
    async_session: AsyncSession, db_connection, vault: Vault
) -> None:
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id)
    before = await storage_crud.get_info(async_session, storage.id)
    storage_id, weapon_id = storage.id, weapon.id

    with pytest.raises(RuntimeError, match="injected delete failure"):
        async with fail_sql(async_session, _deletes_item, "injected delete failure"):
            await item_service.scrap_item(async_session, item_id=weapon_id, model=Weapon)
    # A listener raising mid-flush leaves this session poisoned; read the outcome on a fresh one.
    await async_session.close()
    async with fresh_session(db_connection) as session:
        assert await crud.weapon.get_or_none(session, weapon_id) is not None, "the item must survive a failed scrap"
        assert await _junk_rows(session, storage_id) == [], "a failed scrap must not grant junk"
        after = await storage_crud.get_info(session, storage_id)
    assert after == before, "the storage counters must be unchanged by a failed scrap"


async def test_scrap_does_no_database_work_after_its_commit(async_session: AsyncSession, vault: Vault) -> None:
    """The commit must be the last thing before delivery: post-commit SQL can fail on durable work."""
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id)

    with patch("app.core.event_bus.event_bus.emit", new=AsyncMock()):
        async with record_statements(async_session) as (statements, commit_marks):
            await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)

    assert len(commit_marks) == 1
    trailing = statements[commit_marks[0] :]
    assert not trailing, f"{len(trailing)} statements ran after the scrap commit: {trailing}"


async def test_repeat_scrap_hits_the_same_not_found_error(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id, RarityEnum.COMMON)

    with patch("app.core.event_bus.event_bus.emit", new=AsyncMock()) as emit:
        first = await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)
        commits = counting_commit(async_session)
        with pytest.raises(ResourceNotFoundException):
            await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)

    assert commits == [], "a rejected repeat must not commit anything"
    assert len(await _junk_rows(async_session, storage.id)) == len(first), "a repeat must not grant extra junk"
    assert emit.await_count == 1, "the rejected repeat must not publish a second ITEM_SCRAPPED"
