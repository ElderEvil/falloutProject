"""Cross-worker tick locks: the worker that loses the race must skip, not double-process.

The lock itself is PostgreSQL-only, so these pin the caller-side contract with a
stand-in that reports the lock as already held.
"""

from contextlib import asynccontextmanager
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.services.combat.arena_service import ArenaService
from app.services.combat.incident_service import incident_service


@asynccontextmanager
async def _lock_held_by_another_worker(*_args, **_kwargs):
    """Stand-in for hold_advisory_lock when another worker owns the lock."""
    yield False


@pytest.mark.asyncio
async def test_incident_tick_skips_when_the_lock_is_held(async_session: AsyncSession) -> None:
    with patch("app.services.combat.incident_tick.db_locks.hold_advisory_lock", new=_lock_held_by_another_worker):
        result = await incident_service.process_all_vaults_incidents(async_session, 2)

    assert result == {"vaults": 0, "spawned": 0, "resolved": 0}


@pytest.mark.asyncio
async def test_arena_tick_skips_when_the_lock_is_held(async_session: AsyncSession) -> None:
    with patch("app.services.combat.arena_service.db_locks.hold_advisory_lock", new=_lock_held_by_another_worker):
        result = await ArenaService().process_arena_ticks(async_session, 60)

    assert result == {"arena": {"rooms": 0, "rounds": []}}


@pytest.mark.asyncio
async def test_arena_vault_round_skips_when_the_lock_is_held(async_session: AsyncSession) -> None:
    with patch("app.services.combat.arena_service.db_locks.hold_advisory_lock", new=_lock_held_by_another_worker):
        result = await ArenaService().process_arena_fights(async_session, uuid4(), 60)

    assert result == {"arena": {"rooms": 0, "rounds": []}}


@pytest.mark.asyncio
async def test_lock_helper_is_a_noop_off_postgresql(async_session: AsyncSession) -> None:
    """SQLite has no advisory locks, so the helper must yield True without locking."""
    async with db_locks.hold_advisory_lock(async_session, "test-noop") as acquired:
        assert acquired is True
