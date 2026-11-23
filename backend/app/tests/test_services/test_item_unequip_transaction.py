"""Unequipping an item owns one transaction boundary (real session).

SERVICE_LAYER.md "Transaction ownership": unequipping moves one row back to the vault's
storage and clears the dweller's equipment slot. Both writes belong to a single operation, so
the service entry point stages them through CRUD, commits once, and the endpoint keeps no
session lifecycle. Today the weapon/outfit endpoints reached ``CRUDItem.unequip`` directly and
CRUD owned that commit. These tests pin the target contract on the test database: one commit
per unequip, every write durable on success, nothing surviving a failure at the later write,
no database work after the commit, and a repeated request hitting the same not-found error.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy import event, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.services.item_service import item_service
from app.utils.exceptions import ResourceNotFoundException

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


def _writes_item(statement: str) -> bool:
    """The unequip's single write: the item row moves to storage and loses its dweller."""
    return statement.lower().startswith("update weapon")


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
        # Mark the boundary after the flush: the commit itself emits the staged UPDATEs.
        commit_marks.append(len(statements))

    event.listen(connection, "before_cursor_execute", hook)
    async_session.commit = counting_commit  # type: ignore[method-assign]
    try:
        yield statements, commit_marks
    finally:
        event.remove(connection, "before_cursor_execute", hook)


async def _vault_storage(async_session: AsyncSession, vault_id: UUID) -> Storage:
    """The vault's own storage row; the unequip query joins through it."""
    storage = await storage_crud.get_by_vault(async_session, vault_id)
    if storage is None:
        storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


def _counting_commit(session: AsyncSession) -> list[int]:
    commits: list[int] = []
    original_commit = session.commit

    async def counting_commit() -> None:
        commits.append(1)
        await original_commit()

    session.commit = counting_commit  # type: ignore[method-assign]
    return commits


async def test_unequip_commits_once_and_persists_both_writes(
    async_session: AsyncSession, equipped_dweller: tuple[Dweller, object, Weapon]
) -> None:
    dweller, _, weapon = equipped_dweller
    weapon_id, dweller_id = weapon.id, dweller.id
    storage = await _vault_storage(async_session, dweller.vault_id)
    commits = _counting_commit(async_session)

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
        async with _fail_sql(async_session, _writes_item, "injected item failure"):
            await item_service.unequip_item(async_session, item_id=weapon_id, model=Weapon)
    # A listener raising mid-flush leaves this session poisoned; read the outcome on a fresh one.
    await async_session.close()
    async with AsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
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

    async with _record_statements(async_session) as (statements, commit_marks):
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
    commits = _counting_commit(async_session)

    with pytest.raises(ResourceNotFoundException):
        await item_service.unequip_item(async_session, item_id=weapon.id, model=Weapon)

    assert commits == [], "a rejected repeat must not commit anything"
