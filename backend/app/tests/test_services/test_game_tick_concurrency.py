"""Regression test for overlapping game-tick objective event handling.

``EventBus.emit`` serializes handlers *within one emission*, but two game-loop
tasks can emit ``RESOURCE_COLLECTED`` concurrently. Objective evaluators open
sessions from the module-global session maker, so overlapping emits can issue
two queries through one guarded asyncpg connection and trigger
``InterfaceError: another operation is in progress``.

The test below gives every evaluator session one shared connection and makes
its first query yield before it finishes. A concurrent query then reliably
trips the same single-operation invariant enforced by asyncpg.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.event_bus import EventBus, GameEvent
from app.services.objective_evaluators import ObjectiveEvaluator

logger = logging.getLogger(__name__)


class _ConcurrencyGuardedSession(AsyncSession):
    """AsyncSession that enforces asyncpg's one-operation-at-a-time rule."""

    _in_flight: int = 0
    collisions: int = 0
    executions: int = 0

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        if _ConcurrencyGuardedSession._in_flight > 0:
            _ConcurrencyGuardedSession.collisions += 1
            raise asyncpg.InterfaceError("another operation is in progress")

        _ConcurrencyGuardedSession._in_flight += 1
        try:
            # Force a scheduling point while this simulated connection is busy
            # so the second overlapping emit deterministically hits the guard.
            await asyncio.sleep(0)
            _ConcurrencyGuardedSession.executions += 1
            return await super().execute(*args, **kwargs)
        finally:
            _ConcurrencyGuardedSession._in_flight -= 1


@pytest_asyncio.fixture
async def throwaway_engine() -> AsyncGenerator:
    """Single-connection throwaway engine (SQLite in-memory, StaticPool).

    Uses StaticPool so every session that binds to this engine shares ONE
    underlying DBAPI connection — mirroring ``pool_size=1`` with asyncpg.
    Does NOT touch real PostgreSQL.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(SQLModel.metadata, "before_create")
    def _replace_jsonb_with_json(target, connection, **kw):
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    event.remove(SQLModel.metadata, "before_create", _replace_jsonb_with_json)


def _make_shared_session_maker(shared_conn: AsyncConnection) -> Any:
    """Return a callable mimicking ``async_session_maker`` bound to shared_conn.

    Every call returns a fresh ``_ConcurrencyGuardedSession`` that shares the
    single ``shared_conn`` — so two handler sessions issue queries against
    the SAME connection, reproducing the asyncpg collision.
    """

    def _maker() -> _ConcurrencyGuardedSession:
        return _ConcurrencyGuardedSession(
            bind=shared_conn,
            expire_on_commit=False,
            autoflush=False,
        )

    return _maker


class _CollectLikeEvaluator(ObjectiveEvaluator):
    """Minimal evaluator that uses the production objective query path."""

    objective_type = "collect"
    subscribed_events = (GameEvent.RESOURCE_COLLECTED,)

    def _matches(self, objective: Any, event_type: str, data: dict[str, Any]) -> bool:
        return True


@pytest.mark.asyncio
async def test_overlapping_resource_collected_emits_do_not_collide_on_objective_connection(
    throwaway_engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent ticks must serialize evaluator database access per connection."""
    from unittest.mock import patch

    # Isolation: reset the class-level guard state between tests.
    _ConcurrencyGuardedSession._in_flight = 0
    _ConcurrencyGuardedSession.collisions = 0
    _ConcurrencyGuardedSession.executions = 0

    # Check out the single shared connection AFTER table creation (StaticPool
    # reuses the same underlying connection, so seeded/created state is visible)
    shared_conn = await throwaway_engine.connect()
    shared_maker = _make_shared_session_maker(shared_conn)

    bus = EventBus()
    try:
        # One evaluator is sufficient: the collision comes from two overlapping
        # event emissions, as happens when game-loop tasks overlap.
        _CollectLikeEvaluator(bus)

        vault_id = UUID4("00000000-0000-0000-0000-000000000001")

        with (
            patch("app.services.objective_evaluators.async_session_maker", shared_maker),
            caplog.at_level(logging.ERROR, logger="app.services.event_bus"),
        ):
            await asyncio.gather(
                bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault_id,
                    {"resource_type": "caps", "amount": 10},
                ),
                bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault_id,
                    {"resource_type": "food", "amount": 5},
                ),
            )

        interface_errors = [
            record
            for record in caplog.records
            if record.exc_info and isinstance(record.exc_info[1], asyncpg.InterfaceError)
        ]
        assert _ConcurrencyGuardedSession.collisions == 0
        assert _ConcurrencyGuardedSession.executions == 2
        assert not interface_errors
    finally:
        bus.clear()
        _ConcurrencyGuardedSession._in_flight = 0
        _ConcurrencyGuardedSession.collisions = 0
        _ConcurrencyGuardedSession.executions = 0
        await shared_conn.close()
