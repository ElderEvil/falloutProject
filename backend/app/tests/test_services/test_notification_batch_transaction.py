"""One notification event that yields several rows owns one transaction boundary (real session).

``notify_radio_new_dweller`` is the recruit announcement plus the room-unlock summary it
crosses. Today each row was created by ``CRUDNotification.create`` with its own commit, and the
recruit push went out before the summary row existed -- so a failure while building the summary
left a delivered notification for a recruit the caller might still roll back. SERVICE_LAYER.md
"Reviewing a composed write" (step 4) requires the notification rows to commit with the
operation and every push to follow that commit. These tests pin it on the test database: one
commit for the pair, both rows durable before any delivery, no database work after the commit,
and no row or delivery when a later write fails.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationType
from app.models.notification import Notification
from app.schemas.dweller import DwellerCreate
from app.services.notification_service import NotificationService
from app.tests.factory.dwellers import create_random_common_dweller

pytestmark = pytest.mark.asyncio

SUMMARY_READ = "app.services.notification_service.get_static_game_data"
UNLOCK_POPULATION = 15


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
        commit_marks.append(len(statements))

    event.listen(connection, "before_cursor_execute", hook)
    async_session.commit = counting_commit  # type: ignore[method-assign]
    try:
        yield statements, commit_marks
    finally:
        event.remove(connection, "before_cursor_execute", hook)


@asynccontextmanager
async def _trace_boundary(async_session: AsyncSession) -> AsyncGenerator[list[object]]:
    """Record commit and delivery order on one timeline: the pushes must land after the commit."""
    timeline: list[object] = []
    original_commit = async_session.commit

    async def counting_commit() -> None:
        await original_commit()
        timeline.append("commit")

    async def record_delivery(user_id: UUID, payload: dict) -> None:
        timeline.append(("deliver", payload["notification"]["notification_type"]))

    async_session.commit = counting_commit  # type: ignore[method-assign]
    with patch.object(NotificationService, "_deliver", new=AsyncMock(side_effect=record_delivery)):
        yield timeline


async def _fill_vault(async_session: AsyncSession, vault_id: UUID) -> None:
    """Reach the first room-unlock threshold so the recruit event also writes a summary row."""
    while await crud.dweller.count_alive_in_vault(async_session, vault_id) < UNLOCK_POPULATION:
        await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault_id)
        )
    await async_session.commit()


async def _notification_rows(async_session: AsyncSession, vault_id: UUID) -> list[Notification]:
    result = await async_session.execute(
        select(Notification).where(Notification.vault_id == vault_id).order_by(Notification.created_at)
    )
    return list(result.scalars().all())


async def test_recruit_event_commits_once_and_delivers_both_rows_after_commit(
    async_session: AsyncSession, vault
) -> None:
    await _fill_vault(async_session, vault.id)

    async with _trace_boundary(async_session) as timeline:
        await NotificationService.notify_radio_new_dweller(
            async_session, user_id=vault.user_id, vault_id=vault.id, dweller_name="Nora"
        )

    commits = [mark for mark in timeline if mark == "commit"]
    deliveries = [mark for mark in timeline if isinstance(mark, tuple)]
    assert len(commits) == 1, f"the recruit event committed {len(commits)} times; the service owns exactly one"
    assert timeline[0] == "commit", f"a notification was delivered before its commit: {timeline}"
    assert [mark[1] for mark in deliveries] == [
        NotificationType.RADIO_NEW_DWELLER,
        NotificationType.ROOM_UNLOCKED,
    ], f"both notification rows must be pushed, after the commit: {timeline}"
    types = {row.notification_type for row in await _notification_rows(async_session, vault.id)}
    assert types == {NotificationType.RADIO_NEW_DWELLER, NotificationType.ROOM_UNLOCKED}


async def test_recruit_event_does_no_database_work_after_its_commit(async_session: AsyncSession, vault) -> None:
    await _fill_vault(async_session, vault.id)

    with patch.object(NotificationService, "_deliver", new=AsyncMock()):
        async with _record_statements(async_session) as (statements, commit_marks):
            await NotificationService.notify_radio_new_dweller(
                async_session, user_id=vault.user_id, vault_id=vault.id, dweller_name="Nora"
            )

    assert len(commit_marks) == 1
    trailing = statements[commit_marks[0] :]
    assert not trailing, f"{len(trailing)} statements ran after the recruit commit: {trailing}"
    inserts = [
        statement for statement in statements[: commit_marks[0]] if "insert into notification" in statement.lower()
    ]
    assert len(inserts) == 2, "both notification rows must be inserted before the single commit"


async def test_failure_building_the_summary_leaves_no_row_and_no_delivery(
    async_session: AsyncSession, vault, db_connection
) -> None:
    await _fill_vault(async_session, vault.id)
    vault_id = vault.id

    with (
        patch.object(NotificationService, "_deliver", new=AsyncMock()) as deliver,
        patch(SUMMARY_READ, new=AsyncMock(side_effect=RuntimeError("summary lookup failed"))),
        pytest.raises(RuntimeError, match="summary lookup failed"),
    ):
        await NotificationService.notify_radio_new_dweller(
            async_session, user_id=vault.user_id, vault_id=vault_id, dweller_name="Nora"
        )

    deliver.assert_not_awaited()
    await async_session.rollback()
    async with AsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        count = (
            await session.execute(
                select(func.count()).select_from(Notification).where(Notification.vault_id == vault_id)
            )
        ).scalar_one()
    assert count == 0, "a failed event must not leave a notification row behind"
