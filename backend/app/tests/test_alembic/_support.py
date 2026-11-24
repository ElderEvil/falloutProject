"""Shared plumbing for Alembic fragment tests: load a version file, run it on SQLite."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"
BASELINE_VERSIONS = Path(__file__).resolve().parents[2] / "alembic/baseline_versions"


def migration_path(name: str, directory: Path = VERSIONS) -> Path:
    """Resolve a version filename, or a bare revision, to its single file."""
    if name.endswith(".py"):
        return directory / name
    matches = sorted(directory.glob(f"*-{name}_*.py"))
    assert len(matches) == 1, f"expected one migration for {name}, found {matches}"
    return matches[0]


def load_migration(name: str, module_name: str, directory: Path = VERSIONS) -> ModuleType:
    path = migration_path(name, directory)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def sqlite_db(*ddl: str) -> Generator[sa.Connection]:
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            for statement in ddl:
                connection.exec_driver_sql(statement)
            yield connection
    finally:
        engine.dispose()


def bind_op(module: ModuleType, connection: sa.Connection) -> None:
    module.op = Operations(MigrationContext.configure(connection))


def column_names(connection: sa.Connection, table: str) -> list[str]:
    return [column[1] for column in connection.exec_driver_sql(f"PRAGMA table_info({table})")]


@pytest.fixture(scope="session")
def pg_worker_database() -> Generator[str | None]:
    """A PostgreSQL database private to this xdist worker, migrated and dropped per session.

    The integration suites write real rows outside the savepoint fixture, so one shared database
    lets two workers collide on unique keys — the first symptom was a duplicate user handle in an
    accept race. Cloning the shared database with `TEMPLATE` would be faster but needs exclusive
    access to it, which a parallel worker cannot guarantee; an empty database plus one
    `alembic upgrade head` per worker is deterministic and costs a few seconds once.
    """
    clone = _worker_database_name()
    if clone is None:
        yield None
        return
    url = make_url(str(settings.ASYNC_DATABASE_URI))
    clone_uri = url.set(database=clone).render_as_string(hide_password=False)
    if not _run_admin(url, f'DROP DATABASE IF EXISTS "{clone}" WITH (FORCE)', f'CREATE DATABASE "{clone}"'):
        yield None
        return
    try:
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(Path(__file__).resolve().parents[3]),
            # `str(URL)` renders the password as `***`; the subprocess needs the real one.
            # Alembic then passes the value through configparser, which treats `%` as an
            # interpolation marker, so escape it (a socket-path DSN hits exactly that).
            env={**os.environ, "ASYNC_DATABASE_URI": clone_uri.replace("%", "%%")},
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if migrated.returncode != 0:
            raise RuntimeError(f"alembic upgrade failed for {clone}:\n{migrated.stderr[-2000:]}")
        yield clone
    finally:
        _run_admin(url, f'DROP DATABASE IF EXISTS "{clone}" WITH (FORCE)')


def _run_admin(url, *statements: str) -> bool:
    """Run maintenance-database DDL, reporting whether the server was reachable at all."""
    try:
        asyncio.run(_admin(url, statements))
    except OSError, sa.exc.SQLAlchemyError:
        return False
    return True


async def _admin(url, statements: tuple[str, ...]) -> None:
    # CREATE/DROP DATABASE cannot run inside a transaction block.
    engine = create_async_engine(url.set(database="postgres"), poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(sa.text(statement))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine(request, pg_worker_database: str | None):
    """An engine on this worker's own migrated database, or a skip when Postgres is unreachable.

    Identities are counted on the way in and out: a module that commits a `user`, `vault` or
    `dweller` and leaves it behind is what poisoned a neighbouring module's accept race (a
    duplicate handle), and the per-worker database only bounds the damage to one worker.
    """
    if pg_worker_database is None:
        pytest.skip("PostgreSQL unavailable")
    url = make_url(str(settings.ASYNC_DATABASE_URI)).set(database=pg_worker_database)
    engine = create_async_engine(url, poolclass=NullPool)
    tracked_from = len(_TRACKED)
    before = await _sentinel_counts(engine)
    try:
        yield engine
    finally:
        rows = _TRACKED[tracked_from:]
        del _TRACKED[tracked_from:]
        if rows:
            await _delete_tracked_rows(engine, rows)
        after = await _sentinel_counts(engine)
        await engine.dispose()
    leaked = {table: after[table] - before[table] for table in before if after[table] > before[table]}
    if leaked:
        raise AssertionError(
            f"{request.module.__name__} leaves committed identities behind: {leaked}. "
            "Delete what the test created, or take the rows back inside the same transaction — "
            "they survive into the next module that shares this worker's database."
        )


# Identities, not fixtures: reference content (quest catalog, item catalogs, game config) is
# legitimately rewritten by seeding modules, so counting it would flag correct behaviour.
LEAK_SENTINELS = ("user", "vault", "dweller")

_TRACKED: list[tuple[str, object]] = []


def track_created_identity(*, user_id: object = None, vault_id: object = None) -> None:
    """Register a committed row so the module teardown deletes it.

    Concurrency suites need real commits, but a committed `user` or `vault` outlives the module
    and its handle can collide with the next one — the leak that surfaced as
    `ResourceConflictException: User already exists` in an unrelated accept race.
    """
    for table, row_id in (("user", user_id), ("vault", vault_id)):
        if row_id is not None:
            _TRACKED.append((table, row_id))


async def _delete_tracked_rows(engine, rows: list[tuple[str, object]]) -> None:
    users = [row_id for table, row_id in rows if table == "user"]
    vaults = [row_id for table, row_id in rows if table == "vault"]
    async with engine.begin() as connection:
        # `notification` holds a RESTRICT foreign key to both `user` and `dweller`, so it goes
        # first; vaults then cascade their dwellers, duels and notifications.
        if users:
            await connection.execute(sa.text("DELETE FROM notification WHERE user_id = ANY(:ids)"), {"ids": users})
        if vaults:
            await connection.execute(sa.text("DELETE FROM vault WHERE id = ANY(:ids)"), {"ids": vaults})
        if users:
            await connection.execute(sa.text('DELETE FROM "user" WHERE id = ANY(:ids)'), {"ids": users})


def _worker_database_name() -> str | None:
    url = make_url(str(settings.ASYNC_DATABASE_URI))
    if url.get_backend_name() != "postgresql":
        return None
    return f"{url.database}_w{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"


async def _sentinel_counts(engine) -> dict[str, int]:
    async with engine.connect() as connection:
        return {
            # Table names come from the frozen LEAK_SENTINELS tuple, never from input.
            table: (await connection.execute(sa.text(f'SELECT count(*) FROM "{table}"'))).scalar_one()  # ruff: ignore[hardcoded-sql-expression]
            for table in LEAK_SENTINELS
        }
