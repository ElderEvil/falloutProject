from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core import db_locks

pytest_plugins = ["app.tests.test_alembic._support"]


async def _can_take(engine: AsyncEngine, key: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": key})
        acquired = bool(result.scalar())
        if acquired:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": key})
        return acquired


def _session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _pooled_engine(engine: AsyncEngine) -> AsyncEngine:
    # A pooled engine on the same per-worker database: NullPool cannot show whether a
    # connection was handed back, and advisory locks are per-database. `str(URL)` would
    # mask the password as `***`, so render it with the credential intact.
    return create_async_engine(engine.url.render_as_string(hide_password=False))


@pytest.mark.integration
async def test_lock_excludes_another_connection(live_pg_engine: AsyncEngine) -> None:
    key = "test-688-exclusion"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True
        assert await _can_take(live_pg_engine, key) is False


@pytest.mark.integration
async def test_lock_survives_a_session_commit(live_pg_engine: AsyncEngine) -> None:
    key = "test-688-commit"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True
        await session.commit()
        assert await _can_take(live_pg_engine, key) is False


@pytest.mark.integration
async def test_lock_is_released_when_the_block_exits(live_pg_engine: AsyncEngine) -> None:
    key = "test-688-release"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True
    assert await _can_take(live_pg_engine, key) is True


@pytest.mark.integration
async def test_lock_connection_is_handed_back_on_exit(live_pg_engine: AsyncEngine) -> None:
    engine = _pooled_engine(live_pg_engine)
    try:
        async with (
            _session_maker(engine)() as session,
            db_locks.hold_advisory_lock(session, "test-688-pool-release") as acquired,
        ):
            assert acquired is True
            assert engine.pool.checkedout() >= 1
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_lock_connection_is_handed_back_when_acquisition_fails(live_pg_engine: AsyncEngine) -> None:
    engine = _pooled_engine(live_pg_engine)
    try:
        async with _session_maker(engine)() as session:
            with (
                patch.object(db_locks, "_LOCK_SQL", text("SELECT no_such_function_688()")),
                pytest.raises(SQLAlchemyError),
            ):
                async with db_locks.hold_advisory_lock(session, "test-688-fail"):
                    pass
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_caller_owned_connection_in_a_transaction_is_rejected(live_pg_engine: AsyncEngine) -> None:
    async with live_pg_engine.connect() as conn:
        session = AsyncSession(bind=conn)
        await conn.execute(text("SELECT 1"))
        with pytest.raises(ValueError, match="autocommit connection"):
            async with db_locks.hold_advisory_lock(session, "test-688-ownconn"):
                pass
