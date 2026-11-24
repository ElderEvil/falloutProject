"""Shared plumbing for Alembic fragment tests: load a version file, run it on SQLite."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from collections.abc import Generator
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
    url = make_url(str(settings.ASYNC_DATABASE_URI))
    if url.get_backend_name() != "postgresql":
        yield None
        return
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    clone = f"{url.database}_w{worker}"
    if not _run_admin(url, f'DROP DATABASE IF EXISTS "{clone}" WITH (FORCE)', f'CREATE DATABASE "{clone}"'):
        yield None
        return
    try:
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(Path(__file__).resolve().parents[3]),
            # Alembic hands this through configparser, which treats `%` as an interpolation
            # marker: a socket-path URL would blow up there, so escape it on the way in.
            env={**os.environ, "ASYNC_DATABASE_URI": str(url.set(database=clone)).replace("%", "%%")},
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
async def live_pg_engine(pg_worker_database: str | None):
    """An engine on this worker's own migrated database, or a skip when Postgres is unreachable."""
    if pg_worker_database is None:
        pytest.skip("PostgreSQL unavailable")
    url = make_url(str(settings.ASYNC_DATABASE_URI)).set(database=pg_worker_database)
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()
