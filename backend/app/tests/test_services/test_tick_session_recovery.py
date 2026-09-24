"""Session recovery for tick sweeps (task-session robustness).

A failed statement aborts the transaction, so every later statement on the same
session fails until it is rolled back. Tick phases catch per-entity errors and
keep going, so without a rollback one bad entity fails the rest of the sweep —
and the deferred notifications/level-ups queued on the dead transaction must be
dropped with it. These tests pin both the failure mode and the recovery.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, MissingGreenlet, SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.services.game_tick.guard import guard_phase, recover_session, refresh_after_recovery


async def test_raw_tick_session_recovers_after_a_failed_write() -> None:
    """The production shape: a raw session (no savepoint) is usable again after recovery.

    Rolling back discards the failed transaction's uncommitted work, which is
    exactly why the deferred notifications/level-ups queued on it must be dropped
    too rather than delivered later.
    """
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE widget (id INTEGER PRIMARY KEY)"))

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            await session.execute(text("INSERT INTO widget (id) VALUES (1)"))

            with pytest.raises(IntegrityError):
                await session.execute(text("INSERT INTO widget (id) VALUES (1)"))

            await recover_session(session)

            # The session serves writes again; the rolled-back write is gone.
            await session.execute(text("INSERT INTO widget (id) VALUES (2)"))
            assert (await session.execute(text("SELECT id FROM widget"))).scalars().all() == [2]
    finally:
        await engine.dispose()


async def test_recover_session_restores_a_usable_session(async_session: AsyncSession) -> None:
    """After recovery the same session serves later statements again."""
    with pytest.raises(SQLAlchemyError):
        await async_session.execute(text("SELECT * FROM table_that_does_not_exist"))

    await recover_session(async_session)

    assert (await async_session.execute(text("SELECT 1"))).scalar_one() == 1


async def test_recover_session_discards_deferred_side_effects(async_session: AsyncSession) -> None:
    """Work queued for after the next commit dies with the rolled-back transaction."""
    async_session.info["deferred_notification_deliveries"] = ["stale"]
    async_session.info["deferred_level_up_deliveries"] = ["stale"]

    await recover_session(async_session)

    assert "deferred_notification_deliveries" not in async_session.info
    assert "deferred_level_up_deliveries" not in async_session.info


async def test_guard_phase_recovers_the_session_on_a_database_error(async_session: AsyncSession) -> None:
    """A guarded DB error rolls back, so the caller can keep using the session."""

    async def failing() -> None:
        await async_session.execute(text("SELECT * FROM table_that_does_not_exist"))

    error = await guard_phase("failing step", failing, catch=(SQLAlchemyError,), db_session=async_session)

    assert error is not None
    assert (await async_session.execute(text("SELECT 1"))).scalar_one() == 1


async def test_refresh_after_recovery_unexpires_entities(async_session: AsyncSession) -> None:
    """A sweep may touch its loaded entities again only after they are reloaded.

    recover_session expires every loaded instance, so the next attribute access
    would otherwise trigger an implicit async refresh (MissingGreenlet) and abort
    the rest of the sweep.
    """
    user = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="refresh-test", email="refresh-test@example.com", password="testpass123"),
    )

    # Expire exactly the way a rollback does.
    async_session.expire_all()
    with pytest.raises(MissingGreenlet):
        _ = user.username

    await refresh_after_recovery(async_session, [user])

    assert user.username is not None


async def test_refresh_after_recovery_skips_non_mapped_entities(async_session: AsyncSession) -> None:
    """Test doubles and other non-ORM objects are skipped, not refreshed."""
    await refresh_after_recovery(async_session, [object(), "not-an-entity"])


async def test_guard_phase_lets_later_entities_proceed_after_one_fails(async_session: AsyncSession) -> None:
    """The isolation contract: one bad entity does not fail the rest of the sweep."""
    ran: list[str] = []

    async def bad_entity() -> None:
        ran.append("bad")
        await async_session.execute(text("SELECT * FROM table_that_does_not_exist"))

    async def good_entity() -> None:
        ran.append("good")
        await async_session.execute(text("SELECT 1"))

    first = await guard_phase("bad", bad_entity, catch=(SQLAlchemyError,), db_session=async_session)
    second = await guard_phase("good", good_entity, catch=(SQLAlchemyError,), db_session=async_session)

    assert first is not None
    assert second is None
    assert ran == ["bad", "good"]
