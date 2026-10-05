"""Regression coverage for the world-snapshot activation-pointer migration.

Fragment assertions pin the revision chain without a database; the real
upgrade/downgrade runs against the isolated scratch database supplied by the
local ``harness`` fixture (never the application database). The new columns are
additive and default ``is_active`` to false, so existing snapshots stay
candidates until an operator activates one.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.tests.test_alembic.test_data_migrations import MigrationHarness, _run_sql

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_10_05_0002-a9b8c7d6e5f4_add_world_snapshot_activation.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_world_snapshot_activation", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)

REVISION = "a9b8c7d6e5f4"
PARENT = "862c04111ec1"


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[MigrationHarness]:
    """A disposable scratch database with the app's own credentials; dropped afterwards."""
    if make_url(str(settings.ASYNC_DATABASE_URI)).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping the migration harness")

    app_url = str(settings.ASYNC_DATABASE_URI)
    base_url = make_url(app_url)
    name = f"fallout_migration_test_{uuid.uuid4().hex[:12]}"
    scratch_url = base_url.set(database=name).render_as_string(hide_password=False)

    try:
        asyncio.run(_run_sql(app_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        asyncio.run(_run_sql(app_url, f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # broad by design: any connection problem means "no database here"
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    monkeypatch.setattr(settings, "ASYNC_DATABASE_URI", scratch_url)
    try:
        yield MigrationHarness(scratch_url)
    finally:
        asyncio.run(_run_sql(app_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.mark.integration
class TestWorldSnapshotActivationMigrationFragment:
    """The migration declares the right chain without touching a database."""

    def test_revision_chain(self) -> None:
        assert MIGRATION.revision == REVISION
        assert MIGRATION.down_revision == PARENT


@pytest.mark.integration
class TestWorldSnapshotActivationMigrationRoundTrip:
    """Columns and the partial unique index appear on upgrade and vanish on downgrade."""

    def test_upgrade_adds_pointer_and_guards_one_active_per_world(self, harness: MigrationHarness) -> None:
        harness.upgrade(REVISION)

        columns = {
            row[0]
            for row in harness.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'worldsnapshot'"
            )
        }
        assert {"is_active", "activated_at"} <= columns
        indexes = {
            row[0] for row in harness.fetch("SELECT indexname FROM pg_indexes WHERE tablename = 'worldsnapshot'")
        }
        assert "uq_worldsnapshot_active_world" in indexes

        # Existing rows default to inactive: a stored candidate is never active implicitly.
        harness.execute(
            "INSERT INTO worldsnapshot "
            "(id, world_id, generator_version, seed, config, recipe_fingerprint, "
            " snapshot_checksum, terrain, slots, anchors) "
            "VALUES (gen_random_uuid(), 'wasteland-atlas', 1, 's', '{}'::jsonb, 'fp', 'ck', "
            " '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
        )
        assert harness.scalar("SELECT is_active FROM worldsnapshot WHERE generator_version = 1") is False

        harness.execute("UPDATE worldsnapshot SET is_active = true, activated_at = now() WHERE generator_version = 1")
        harness.execute(
            "INSERT INTO worldsnapshot "
            "(id, world_id, generator_version, seed, config, recipe_fingerprint, "
            " snapshot_checksum, terrain, slots, anchors, is_active) "
            "VALUES (gen_random_uuid(), 'wasteland-atlas', 2, 's2', '{}'::jsonb, 'fp2', 'ck2', "
            " '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, false)"
        )
        # Only one active snapshot per world is a database guarantee.
        with pytest.raises(IntegrityError):
            harness.execute("UPDATE worldsnapshot SET is_active = true WHERE generator_version = 2")

        harness.downgrade(PARENT)
        remaining = {
            row[0]
            for row in harness.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'worldsnapshot'"
            )
        }
        assert "is_active" not in remaining
        assert "activated_at" not in remaining
