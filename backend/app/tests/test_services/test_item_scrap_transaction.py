"""Scrapping an item owns one transaction boundary (real session).

SERVICE_LAYER.md "Transaction ownership" and "Reviewing a composed write": a scrap deletes the
weapon/outfit row and inserts one or more junk rows into the same storage, so the service entry
point must stage every row, commit once, and only then deliver ``ITEM_SCRAPPED`` (whose subscriber
records recipe progress on its own session). These tests pin that contract on the test database:
one commit per scrap, every row durable on success, nothing surviving a failure at a later write,
no database work after the commit, and a repeated request hitting the same not-found error instead
of producing a second batch of junk.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
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
from app.utils.exceptions import ResourceNotFoundException
from app.utils.item_factory import build_weapon

pytestmark = pytest.mark.asyncio

FaultHook = Callable[[str], object]


@asynccontextmanager
async def _fail_sql(async_session: AsyncSession, predicate: FaultHook, message: str) -> AsyncGenerator[None]:
    """Raise at the first statement matching ``predicate`` while the block runs."""
    connection = (await async_session.connection()).sync_connection

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if predicate(statement):
            raise RuntimeError(message)

    event.listen(connection, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def _deletes_item(statement: str) -> bool:
    """The item delete is the last write of the staged scrap, after its junk inserts."""
    return statement.lower().startswith("delete from weapon")


@asynccontextmanager
async def _record_statements(async_session: AsyncSession) -> AsyncGenerator[tuple[list[str], list[int]]]:
    """Record every statement and the statement index at which each commit was issued."""
    connection = (await async_session.connection()).sync_connection
    statements: list[str] = []
    commit_marks: list[int] = []

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if not statement.lower().startswith(("savepoint", "release savepoint", "rollback to savepoint", "begin")):
            statements.append(statement)

    original_commit = async_session.commit

    async def counting_commit() -> None:
        await original_commit()
        # Mark the boundary after the flush: the commit itself emits the staged INSERT/DELETE.
        commit_marks.append(len(statements))

    event.listen(connection, "before_cursor_execute", hook)
    async_session.commit = counting_commit  # type: ignore[method-assign]
    try:
        yield statements, commit_marks
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def _counting_commit(session: AsyncSession) -> list[int]:
    commits: list[int] = []
    original_commit = session.commit

    async def counting_commit() -> None:
        commits.append(1)
        await original_commit()

    session.commit = counting_commit  # type: ignore[method-assign]
    return commits


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


async def _count(async_session: AsyncSession, model) -> int:
    return int((await async_session.execute(select(func.count()).select_from(model))).scalar_one())


async def test_scrap_commits_once_and_persists_every_row(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id)
    commits = _counting_commit(async_session)

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
        async with _fail_sql(async_session, _deletes_item, "injected delete failure"):
            await item_service.scrap_item(async_session, item_id=weapon_id, model=Weapon)
    # A listener raising mid-flush leaves this session poisoned; read the outcome on a fresh one.
    await async_session.close()
    async with AsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        assert await crud.weapon.get_or_none(session, weapon_id) is not None, "the item must survive a failed scrap"
        assert await _junk_rows(session, storage_id) == [], "a failed scrap must not grant junk"
        after = await storage_crud.get_info(session, storage_id)
    assert after == before, "the storage counters must be unchanged by a failed scrap"


async def test_scrap_does_no_database_work_after_its_commit(async_session: AsyncSession, vault: Vault) -> None:
    """The commit must be the last thing before delivery: post-commit SQL can fail on durable work."""
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id)

    with patch("app.core.event_bus.event_bus.emit", new=AsyncMock()):
        async with _record_statements(async_session) as (statements, commit_marks):
            await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)

    assert len(commit_marks) == 1
    trailing = statements[commit_marks[0] :]
    assert not trailing, f"{len(trailing)} statements ran after the scrap commit: {trailing}"


async def test_repeat_scrap_hits_the_same_not_found_error(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _storage(async_session, vault)
    weapon = await _weapon(async_session, storage.id, RarityEnum.COMMON)

    with patch("app.core.event_bus.event_bus.emit", new=AsyncMock()) as emit:
        first = await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)
        commits = _counting_commit(async_session)
        with pytest.raises(ResourceNotFoundException):
            await item_service.scrap_item(async_session, item_id=weapon.id, model=Weapon)

    assert commits == [], "a rejected repeat must not commit anything"
    assert len(await _junk_rows(async_session, storage.id)) == len(first), "a repeat must not grant extra junk"
    assert emit.await_count == 1, "the rejected repeat must not publish a second ITEM_SCRAPPED"
