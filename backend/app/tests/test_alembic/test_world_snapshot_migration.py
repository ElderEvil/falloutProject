from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.world_snapshot_service import world_snapshot_service
from app.tests.test_alembic._support import load_migration
from app.tests.test_alembic.test_data_migrations import MigrationHarness

pytest_plugins = ["app.tests.test_alembic.test_data_migrations"]

MIGRATION = load_migration("2026_10_03_0001-a1f2b3c4d5e6_add_world_snapshot.py", "add_world_snapshot")
REVISION = "a1f2b3c4d5e6"
PARENT = "c19031dc6b22"


@pytest.mark.integration
class TestWorldSnapshotMigrationFragment:
    def test_revision_chain(self) -> None:
        assert MIGRATION.revision == REVISION
        assert MIGRATION.down_revision == PARENT


@pytest.mark.integration
class TestWorldSnapshotMigrationRoundTrip:
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
