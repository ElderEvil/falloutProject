"""Structural perf signal for tests: count the SQL statements a block executes.

Wall-clock time in tests is noisy, and SQLite latency is not PostgreSQL latency,
so query *count* is the stable signal for N+1 regressions and for proving that a
batching change actually removed round-trips. Pair it with a wall-time probe
(e.g. ``app/tests/test_services/test_tick_perf.py``) for the full picture.

Usage::

    with count_sql_statements(async_session) as statements:
        await game_loop_service.process_vault_tick(async_session, vault_id)
    print(statements.value)

Call ``reset()`` between phases to attribute statements to a specific step.
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass
class StatementCounter:
    """Mutable statement count for one ``count_sql_statements`` block."""

    value: int = 0

    def reset(self) -> None:
        self.value = 0


def _executable_bind(db_session: AsyncSession) -> Connection | Engine | None:
    """Return the sync bind statements run through, or None when unbound.

    ``AsyncSession.get_bind()`` may hand back a sync Connection/Engine depending
    on how the session was built; async engines and connections must be
    unwrapped because SQLAlchemy rejects listeners on the async wrappers.
    """
    bind = db_session.get_bind()
    if isinstance(bind, AsyncEngine):
        return bind.sync_engine
    if isinstance(bind, AsyncConnection):
        return bind.sync_connection
    if isinstance(bind, (Connection, Engine)):
        return bind
    return None


@contextmanager
def count_sql_statements(db_session: AsyncSession) -> Generator[StatementCounter]:
    """Count statements executed on ``db_session``'s connection for the block."""
    connection = _executable_bind(db_session)
    counter = StatementCounter()
    if connection is None:
        yield counter
        return

    def _on_execute(*_args: object) -> None:
        counter.value += 1

    event.listen(connection, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(connection, "before_cursor_execute", _on_execute)
