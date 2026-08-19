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
import threading
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

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

from app.services import objective_evaluators
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


class _ThreadSafeGuardedSession(AsyncSession):
    """AsyncSession enforcing one in-flight operation per connection, thread-safe.

    State is keyed by the bound connection so that sessions from different
    threads (each with their own connection post-fix) never collide, while
    sessions sharing one connection (pre-fix) deterministically do.
    """

    _state_lock = threading.Lock()
    _in_flight: ClassVar[dict[int, int]] = {}
    collisions: ClassVar[int] = 0
    executions: ClassVar[int] = 0

    @classmethod
    def reset(cls) -> None:
        with cls._state_lock:
            cls._in_flight.clear()
            cls.collisions = 0
            cls.executions = 0

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        conn_key = id(self.bind)
        with _ThreadSafeGuardedSession._state_lock:
            if _ThreadSafeGuardedSession._in_flight.get(conn_key, 0) > 0:
                _ThreadSafeGuardedSession.collisions += 1
                raise asyncpg.InterfaceError("another operation is in progress")
            _ThreadSafeGuardedSession._in_flight[conn_key] = _ThreadSafeGuardedSession._in_flight.get(conn_key, 0) + 1
            _ThreadSafeGuardedSession.executions += 1
        try:
            # Hold the simulated connection busy so a concurrent operation from
            # the other worker thread deterministically trips the guard.
            await asyncio.sleep(0.1)
            return await super().execute(*args, **kwargs)
        finally:
            with _ThreadSafeGuardedSession._state_lock:
                _ThreadSafeGuardedSession._in_flight[conn_key] = (
                    _ThreadSafeGuardedSession._in_flight.get(conn_key, 0) - 1
                )


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


def _make_thread_safe_session_maker(shared_conn: AsyncConnection) -> Any:
    """Return a callable mimicking ``async_session_maker`` bound to shared_conn."""

    def _maker() -> _ThreadSafeGuardedSession:
        return _ThreadSafeGuardedSession(
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


def _seeded_engine() -> tuple[Any, Any, Any]:
    """Create a fresh in-memory engine (SQLite, StaticPool) with schema.

    Returns ``(engine, create_all, dispose)`` so callers control lifecycle
    from their own event loop (``await create_all()`` / ``await dispose()``).
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

    async def _create_all() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def _dispose() -> None:
        await engine.dispose()
        event.remove(SQLModel.metadata, "before_create", _replace_jsonb_with_json)

    return engine, _create_all, _dispose


def test_cross_thread_ticks_do_not_collide_on_shared_objective_connection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dramatiq worker threads (each with its own event loop) must not share one DB connection.

    Production: ``asyncio.run(run_tick())`` runs per worker thread with a fresh
    loop, while objective evaluators open sessions from the module-global
    ``async_session_maker``. Two ticks then issue queries through one pooled
    asyncpg connection -> ``InterfaceError: another operation is in progress``.

    Pre-fix the fix API ``set_current_session_maker`` does not exist, so both
    threads fall back to the patched module-global maker sharing one connection
    and deterministically collide. Post-fix each thread sets its own
    loop-local session maker, so no connection is shared.
    """
    import threading
    from unittest.mock import patch

    _ThreadSafeGuardedSession.reset()

    shared_engine, create_shared, dispose_shared = _seeded_engine()

    async def _connect_shared() -> Any:
        await create_shared()
        return await shared_engine.connect()

    shared_conn = asyncio.run(_connect_shared())
    shared_maker = _make_thread_safe_session_maker(shared_conn)

    bus = EventBus()
    vaults = [
        UUID4("00000000-0000-0000-0000-000000000002"),
        UUID4("00000000-0000-0000-0000-000000000003"),
    ]
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _worker_thread(vault_id: UUID4) -> threading.Thread:
        def _run() -> None:
            async def _main() -> None:
                setter = getattr(objective_evaluators, "set_current_session_maker", None)
                own_conn = None
                own_dispose = None
                if setter is not None:
                    engine, create_all, dispose = _seeded_engine()
                    await create_all()
                    own_conn = await engine.connect()
                    own_dispose = dispose
                    setter(_make_thread_safe_session_maker(own_conn))
                try:
                    barrier.wait(timeout=30)
                    for _ in range(3):
                        await bus.emit(
                            GameEvent.RESOURCE_COLLECTED,
                            vault_id,
                            {"resource_type": "caps", "amount": 10},
                        )
                finally:
                    if own_conn is not None:
                        await own_conn.close()
                        await own_dispose()

            try:
                asyncio.run(_main())
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=_run, name=f"worker-{vault_id}")
        thread.start()
        return thread

    try:
        _CollectLikeEvaluator(bus)

        with (
            patch("app.services.objective_evaluators.async_session_maker", shared_maker),
            caplog.at_level(logging.ERROR, logger="app.services.event_bus"),
        ):
            threads = [_worker_thread(vault_id) for vault_id in vaults]
            for thread in threads:
                thread.join(timeout=60)

        interface_errors = [
            record
            for record in caplog.records
            if record.exc_info and isinstance(record.exc_info[1], asyncpg.InterfaceError)
        ]
        assert not errors, f"worker threads raised: {errors}"
        assert _ThreadSafeGuardedSession.collisions == 0
        assert _ThreadSafeGuardedSession.executions == 6
        assert not interface_errors
    finally:
        bus.clear()
        _ThreadSafeGuardedSession.reset()
        asyncio.run(shared_conn.close())
        asyncio.run(dispose_shared())
