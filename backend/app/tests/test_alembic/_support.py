"""Shared plumbing for Alembic fragment tests: load a version file, run it on SQLite."""

from __future__ import annotations

import importlib.util
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


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine():
    """The migrated application database, or a skip when Postgres is not reachable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL")
    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(sa.text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()
