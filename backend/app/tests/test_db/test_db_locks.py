"""Advisory-lock contract: exclusion across connections, and no leak on exit.

The tick lock has to outlive the per-round commits, which is exactly what a lock
riding the caller's session cannot do. These run against live PostgreSQL (SQLite
has no advisory locks) and skip when it is unavailable.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
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
