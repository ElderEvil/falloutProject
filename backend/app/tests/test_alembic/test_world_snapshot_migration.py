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
def test_road_migration_preserves_world_and_concurrent_backfills_agree(harness: MigrationHarness) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.services.world_snapshot_service import world_snapshot_service

    parent = "c8f2a1b3d4e5"
    revision = "d9a3b2c4e5f6"
    harness.upgrade(parent)
    harness.execute(
        "INSERT INTO worldsnapshot "
        "(id, world_id, generator_version, seed, config, recipe_fingerprint, "
        " snapshot_checksum, terrain, slots, anchors) "
        "VALUES (gen_random_uuid(), 'wasteland-atlas', 1, 'road-migration', "
        "'{\"width\": 2, \"height\": 2}'::jsonb, 'fp', 'original-checksum', "
        '\'["wasteland","wasteland","wasteland","water"]\'::jsonb, \'[]\'::jsonb, \'[]\'::jsonb)'
    )
    base_query = "SELECT terrain, slots, generator_version, recipe_fingerprint, snapshot_checksum FROM worldsnapshot"
    original = harness.fetch(base_query)
    harness.upgrade(revision)
    assert harness.scalar("SELECT roads IS NULL FROM worldsnapshot") is True
    assert harness.fetch(base_query) == original

    async def concurrent_backfill() -> None:
        engine = create_async_engine(harness.url)
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def backfill() -> dict:
            async with maker() as session:
                snapshot = await world_snapshot_service.backfill_roads(session, upgrade=True)
                return snapshot.roads

        try:
            first, second = await asyncio.gather(backfill(), backfill())
            assert first == second
            assert first["base_checksum"] == "original-checksum"
        finally:
            await engine.dispose()

    asyncio.run(concurrent_backfill())
    assert harness.scalar("SELECT roads IS NOT NULL FROM worldsnapshot") is True
    assert harness.fetch(base_query) == original
    harness.execute("UPDATE worldsnapshot SET roads = jsonb_set(roads, '{version}', '1'::jsonb)")
    asyncio.run(concurrent_backfill())
    assert harness.scalar("SELECT roads ->> 'version' FROM worldsnapshot") == "4"
    assert harness.fetch(base_query) == original
    harness.downgrade(parent)
    assert harness.fetch(base_query) == original
