"""Regression test for asyncpg InterfaceError during game-tick objective queries.

Reproduces ``asyncpg.InterfaceError: another operation is in progress`` raised
when ``EventBus.emit`` runs objective-evaluator handlers concurrently via
``asyncio.gather`` while they share a single underlying DB connection.

Context (cited):
    - ``app/services/game_loop.py:127-134`` emits ``RESOURCE_COLLECTED`` once
      per resource type in a serial loop after ``await db_session.commit()``.
    - ``app/services/event_bus.py:54-66`` ``emit`` dispatches to ALL handlers
      via ``asyncio.gather(..., return_exceptions=True)`` — concurrent.
    - ``app/services/objective_evaluators.py:56-72`` each handler opens its
      OWN ``async_session_maker()`` bound to the GLOBAL ``async_engine``
      (``app/db/session.py:9-15``).

When the pool is sized so handlers share a single asyncpg connection (e.g.
``pool_size=1`` in a Dramatiq worker), two concurrent queries on that one
connection raise ``asyncpg.InterfaceError: another operation is in progress``.

Strategy:
    This test forces that scenario with a throwaway in-memory engine whose
    handler sessions all bind to ONE shared ``AsyncConnection``. The session
    class ``_ConcurrencyGuardedSession`` mimics asyncpg's
    one-operation-at-a-time rule: a second ``execute`` while another is in
    flight raises ``asyncpg.InterfaceError``.

    The test FAILS on unpatched code (InterfaceError raised+logged by emit's
    gather) and PASSES once ``emit`` serializes handler execution or handlers
    reuse the caller's session.
"""

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
    """AsyncSession that mimics asyncpg's one-operation-at-a-time rule.

    A single class-level counter tracks in-flight ``execute`` calls. If a
    second coroutine invokes ``execute`` while another is still awaiting its
    DB roundtrip, ``asyncpg.InterfaceError`` is raised — exactly what asyncpg
    does when one connection has two operations in flight concurrently.

    asyncio is cooperative: the check-then-increment below contains no
    ``await``, so it is atomic. The only point control is yielded to the
    event loop is inside ``super().execute(...)`` — which is where the other
    handler gets scheduled and trips the guard.
    """

    _in_flight: int = 0

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        if _ConcurrencyGuardedSession._in_flight > 0:
            raise asyncpg.InterfaceError("another operation is in progress")
        _ConcurrencyGuardedSession._in_flight += 1
        try:
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

    # SQLite has no JSONB; swap JSONB columns to JSON for table creation
    # (same pattern as conftest.db_connection).
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
    """Minimal ObjectiveEvaluator mirroring CollectEvaluator's DB access path.

    Subscribes to ``RESOURCE_COLLECTED`` and issues a SELECT against
    Objective/VaultObjectiveProgressLink — the same query path the real
    ``CollectEvaluator._get_active_objectives`` uses (objective_evaluators.py
    lines 74-89). Two instances subscribed on the same bus make ``emit``'s
    ``asyncio.gather`` run two handler coroutines concurrently.
    """

    objective_type = "collect"
    subscribed_events = [GameEvent.RESOURCE_COLLECTED]

    def _matches(self, objective: Any, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        return True


@pytest.mark.asyncio
async def test_game_tick_resource_collected_does_not_raise_interface_error(
    throwaway_engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RESOURCE_COLLECTED emit loop must not trigger asyncpg.InterfaceError.

    Mirrors ``game_loop.py:127-134``: a serial for-loop emitting
    ``RESOURCE_COLLECTED`` once per resource type. Each emit dispatches to
    multiple evaluator handlers via ``asyncio.gather`` (concurrent). With a
    single shared connection, the unpatched gather-based emit causes two
    handler sessions to issue concurrent queries on one connection ->
    ``asyncpg.InterfaceError: another operation is in progress``.

    This test FAILS on unpatched code (InterfaceError raised+logged by emit)
    and PASSES once emit serializes handlers or handlers reuse the caller
    session.
    """
    from unittest.mock import patch

    # Isolation: reset the class-level guard counter between tests
    _ConcurrencyGuardedSession._in_flight = 0

    # Check out the single shared connection AFTER table creation (StaticPool
    # reuses the same underlying connection, so seeded/created state is visible)
    shared_conn = await throwaway_engine.connect()
    shared_maker = _make_shared_session_maker(shared_conn)

    bus = EventBus()
    try:
        # Register TWO evaluator instances so emit's gather runs two handlers
        # concurrently — both open sessions on the shared connection.
        _CollectLikeEvaluator(bus)
        _CollectLikeEvaluator(bus)

        vault_id = UUID4("00000000-0000-0000-0000-000000000001")

        with (
            patch("app.services.objective_evaluators.async_session_maker", shared_maker),
            caplog.at_level(logging.ERROR, logger="app.services.event_bus"),
        ):
            # Mirror game_loop.py:127-134 — serial emit per resource type
            production = {"caps": 10, "food": 5, "water": 3}
            for resource_type, amount in production.items():
                await bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault_id,
                    {"resource_type": resource_type, "amount": int(amount)},
                )

        interface_errors = [
            rec for rec in caplog.records if rec.exc_info and isinstance(rec.exc_info[1], asyncpg.InterfaceError)
        ]
        assert not interface_errors, (
            f"asyncpg.InterfaceError raised during game-tick emit loop "
            f"({len(interface_errors)} occurrence(s)) — handlers ran concurrently "
            f"on a shared connection: {[str(r.exc_info[1]) for r in interface_errors]}"
        )
    finally:
        bus.clear()
        _ConcurrencyGuardedSession._in_flight = 0
        await shared_conn.close()
