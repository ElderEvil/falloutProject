"""Advisory-lock contract: exclusion across connections, and no leak on exit.

The tick lock has to outlive the per-round commits, which is exactly what a lock
riding the caller's session cannot do. These run against live PostgreSQL (SQLite
has no advisory locks) and skip when it is unavailable.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import db_locks
from app.core.config import settings


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping advisory-lock check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


async def _can_take(engine: AsyncEngine, key: str) -> bool:
    """Whether a fresh connection can take the lock; releases it immediately if it can."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": key})
        acquired = bool(result.scalar())
        if acquired:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": key})
        return acquired


def _session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lock_excludes_another_connection(live_pg_engine: AsyncEngine) -> None:
    key = "test-688-exclusion"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True
        assert await _can_take(live_pg_engine, key) is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lock_survives_a_session_commit(live_pg_engine: AsyncEngine) -> None:
    """A per-round commit must not move the lock off the connection that holds it."""
    key = "test-688-commit"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True
        await session.commit()
        assert await _can_take(live_pg_engine, key) is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lock_is_released_when_the_block_exits(live_pg_engine: AsyncEngine) -> None:
    key = "test-688-release"
    async with _session_maker(live_pg_engine)() as session, db_locks.hold_advisory_lock(session, key) as acquired:
        assert acquired is True

    assert await _can_take(live_pg_engine, key) is True


async def _pooled_engine() -> AsyncEngine:
    """A pooled engine: NullPool cannot show whether a connection was handed back."""
    return create_async_engine(str(settings.ASYNC_DATABASE_URI))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lock_connection_is_handed_back_on_exit(live_pg_engine: AsyncEngine) -> None:
    """The dedicated lock connection must not stay checked out after the block."""
    engine = await _pooled_engine()
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
@pytest.mark.asyncio
async def test_lock_connection_is_handed_back_when_acquisition_fails(live_pg_engine: AsyncEngine) -> None:
    """A failed lock query must still close the connection it opened."""
    engine = await _pooled_engine()
    try:
        async with _session_maker(engine)() as session:
            with patch.object(db_locks, "_LOCK_SQL", text("SELECT no_such_function_688()")):
                with pytest.raises(SQLAlchemyError):
                    async with db_locks.hold_advisory_lock(session, "test-688-fail"):
                        pass
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_caller_owned_connection_in_a_transaction_is_rejected(live_pg_engine: AsyncEngine) -> None:
    """A caller-owned connection cannot be made autocommit, so mid-transaction use is refused."""
    async with live_pg_engine.connect() as conn:
        session = AsyncSession(bind=conn)
        await conn.execute(text("SELECT 1"))

        with pytest.raises(ValueError):
            async with db_locks.hold_advisory_lock(session, "test-688-ownconn"):
                pass
