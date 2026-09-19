"""PostgreSQL advisory locks and connectivity probe for background workers.

Tick actors (incidents, arena, spawning) serialize across workers with
advisory locks; the health check pings the database. Single home for the raw
SQL so services stay query-free and the layer guard keeps passing.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_LOCK_SQL = text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0))")
_UNLOCK_SQL = text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))")


@asynccontextmanager
async def hold_advisory_lock(source: AsyncSession, lock_key: str) -> AsyncIterator[bool]:
    """Hold a session-level advisory lock for a whole block, on one dedicated connection.

    A tick spans many commits, so the lock must not ride the caller's session: after
    each commit SQLAlchemy may hand back a different connection, and the unlock then
    lands on a connection that does not own the lock. PostgreSQL keeps a
    session-level lock on the backend that took it, so it outlives the tick and every
    other worker's ``pg_try_advisory_lock`` returns false - the tick silently stops
    advancing instead of running twice. Holding the lock on a dedicated connection
    keeps acquire and release on the same backend for the whole block, and closing
    that connection releases the lock even if the block raises.

    Yields whether the lock was acquired. Outside PostgreSQL (tests, SQLite) it
    yields True without locking, since SQLite serializes writers itself.
    """
    opened: AsyncConnection | None = None
    bind = source.bind
    if isinstance(bind, AsyncEngine):
        opened = await bind.connect()
        connection: AsyncConnection | None = opened
    elif isinstance(bind, AsyncConnection):
        connection = bind
    else:
        connection = None

    if connection is None or connection.dialect.name != "postgresql":
        try:
            yield True
        finally:
            if opened is not None:
                await opened.close()
        return

    acquired = bool((await connection.execute(_LOCK_SQL, {"lock_key": lock_key})).scalar())
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await connection.execute(_UNLOCK_SQL, {"lock_key": lock_key})
            except Exception:  # broad by design: the lock self-releases on close
                logger.exception("Failed to release advisory lock %s", lock_key)
        if opened is not None:
            await opened.close()


async def try_advisory_xact_lock(db_session: AsyncSession, lock_key: str) -> bool:
    """Acquire a transaction-scoped advisory lock; no-op True outside PostgreSQL."""
    if db_session.get_bind().dialect.name != "postgresql":
        return True

    result = await db_session.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )
    return bool(result.scalar())


async def postgres_ping(engine: AsyncEngine) -> None:
    """Open a connection and run SELECT 1; raises on failure."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
