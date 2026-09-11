"""PostgreSQL advisory locks and connectivity probe for background workers.

Tick actors (incidents, arena, spawning) serialize across workers with
advisory locks; the health check pings the database. Single home for the raw
SQL so services stay query-free and the layer guard keeps passing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

logger = logging.getLogger(__name__)


def _is_postgres(db_session: AsyncSession) -> bool:
    return db_session.get_bind().dialect.name == "postgresql"


async def try_advisory_lock(db_session: AsyncSession, lock_key: str) -> bool:
    """Acquire a session-level advisory lock; no-op True outside PostgreSQL."""
    if not _is_postgres(db_session):
        return True

    result = await db_session.execute(
        text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )
    return bool(result.scalar())


async def release_advisory_lock(db_session: AsyncSession, lock_key: str, *, swallow_errors: bool = False) -> None:
    """Release a session-level advisory lock.

    With swallow_errors, unlock failure is logged instead of raised: the lock
    self-releases on session close, so it must not mask the tick error.
    """
    if not _is_postgres(db_session):
        return
    try:
        await db_session.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )
    except Exception:
        if not swallow_errors:
            raise
        logger.exception("Failed to release advisory lock %s", lock_key)


async def try_advisory_xact_lock(db_session: AsyncSession, lock_key: str) -> bool:
    """Acquire a transaction-scoped advisory lock; no-op True outside PostgreSQL."""
    if not _is_postgres(db_session):
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
