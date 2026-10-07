"""Regression coverage for the world snapshot migration.

Two layers, matching the repo's split:
- fragment assertions pin the revision chain and the created table shape without a DB;
- the real upgrade/downgrade runs against the isolated scratch database via the
  ``harness`` fixture in ``test_data_migrations`` semantics (never the app DB).

The snapshot table is the persistence boundary for the backend-owned world; it is
created exactly once and read thereafter, so the migration must round-trip cleanly.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.tests.test_alembic.test_data_migrations import MigrationHarness, _run_sql

MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/2026_10_03_0001-a1f2b3c4d5e6_add_world_snapshot.py"
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_world_snapshot", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)

REVISION = "a1f2b3c4d5e6"
PARENT = "c19031dc6b22"

MASKS_MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_10_07_0001-e2f3a4b5c6d7_add_world_snapshot_roads_and_rivers.py"
)
MASKS_MIGRATION_SPEC = importlib.util.spec_from_file_location("add_world_snapshot_roads_and_rivers", MASKS_MIGRATION_PATH)
assert MASKS_MIGRATION_SPEC
assert MASKS_MIGRATION_SPEC.loader
MASKS_MIGRATION = importlib.util.module_from_spec(MASKS_MIGRATION_SPEC)
MASKS_MIGRATION_SPEC.loader.exec_module(MASKS_MIGRATION)

MASKS_REVISION = "e2f3a4b5c6d7"
MASKS_PARENT = "862c04111ec1"

_INSERT_LEGACY_ROW = (
    "INSERT INTO worldsnapshot "
    "(id, world_id, generator_version, seed, config, recipe_fingerprint, "
    " snapshot_checksum, terrain, slots, anchors) "
    "VALUES (gen_random_uuid(), 'wasteland-atlas', :version, 's', "
    " '{\"width\": 2, \"height\": 2}'::jsonb, 'fp', 'ck', "
    " '[\"wasteland\"]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[MigrationHarness]:
    """A disposable scratch database with the app's own credentials; dropped afterwards.

    Same contract as ``test_data_migrations.harness``; local so this module can run the
    snapshot migration on its own without the application database ever being the subject.
    """
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
class TestWorldSnapshotMigrationFragment:
    """The migration declares the right chain and table without touching a database."""

    def test_revision_chain(self) -> None:
        assert MIGRATION.revision == REVISION
        assert MIGRATION.down_revision == PARENT


@pytest.mark.integration
class TestWorldSnapshotMigrationRoundTrip:
    """Upgrade creates the table; downgrade removes it; both are clean."""

    def test_upgrade_creates_table_and_downgrade_drops_it(self, harness: MigrationHarness) -> None:
        harness.upgrade(REVISION)

        columns = {
            row[0]
            for row in harness.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'worldsnapshot'"
            )
        }
        assert {
            "id",
            "world_id",
            "generator_version",
            "seed",
            "config",
            "recipe_fingerprint",
            "snapshot_checksum",
            "terrain",
            "slots",
            "anchors",
            "created_at",
            "updated_at",
        } <= columns

        # Insert a row exercising the JSONB payload columns, then read it back.
        harness.execute(
            "INSERT INTO worldsnapshot "
            "(id, world_id, generator_version, seed, config, recipe_fingerprint, "
            " snapshot_checksum, terrain, slots, anchors) "
            "VALUES (gen_random_uuid(), 'wasteland-atlas', 1, 's', '{\"width\": 2, \"height\": 2}'::jsonb, "
            " 'fp', 'ck', '[\"wasteland\"]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
        )
        assert harness.scalar("SELECT count(*) FROM worldsnapshot") == 1

        harness.downgrade(PARENT)
        remaining = harness.fetch("SELECT 1 FROM information_schema.tables WHERE table_name = 'worldsnapshot'")
        assert remaining == []


@pytest.mark.integration
class TestWorldSnapshotMasksMigrationFragment:
    """The roads+rivers migration declares the right chain without touching a database."""

    def test_revision_chain(self) -> None:
        assert MASKS_MIGRATION.revision == MASKS_REVISION
        assert MASKS_MIGRATION.down_revision == MASKS_PARENT


@pytest.mark.integration
class TestWorldSnapshotMasksMigrationRoundTrip:
    """Existing rows get empty roads and rivers defaults; downgrade drops both columns."""

    def test_existing_rows_get_empty_masks_and_downgrade_drops_columns(self, harness: MigrationHarness) -> None:
        harness.upgrade(MASKS_PARENT)
        harness.execute(_INSERT_LEGACY_ROW, version=1)

        harness.upgrade(MASKS_REVISION)

        assert harness.scalar("SELECT roads::text FROM worldsnapshot WHERE generator_version = 1") == "[]"
        assert harness.scalar("SELECT rivers::text FROM worldsnapshot WHERE generator_version = 1") == "[]"
        harness.execute(_INSERT_LEGACY_ROW, version=2)
        assert harness.scalar("SELECT roads::text FROM worldsnapshot WHERE generator_version = 2") == "[]"
        assert harness.scalar("SELECT rivers::text FROM worldsnapshot WHERE generator_version = 2") == "[]"

        harness.downgrade(MASKS_PARENT)
        columns = {
            row[0]
            for row in harness.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'worldsnapshot'"
            )
        }
        assert "roads" not in columns
        assert "rivers" not in columns
