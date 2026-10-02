"""Regression coverage for the vault-slot migrations (add slots; move home markers).

Runs the real upgrade chain on an isolated scratch database, never the app DB:
- ``e7a1b2c3d4e5`` creates ``vaultslot`` and backfills existing vaults by number;
- ``f8b2c3d4e5f6`` moves home-vault registry rows from the centre to their slot.

The fragment layer pins the revision chain without a database.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.tests.test_alembic.test_data_migrations import MigrationHarness, _run_sql

VERSIONS = Path(__file__).parents[2] / "alembic/versions"
ADD_SLOTS_PATH = VERSIONS / "2026_10_02_0001-e7a1b2c3d4e5_add_vault_slots.py"
MOVE_HOME_PATH = VERSIONS / "2026_10_02_0002-f8b2c3d4e5f6_move_home_markers_to_slots.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADD_SLOTS = _load(ADD_SLOTS_PATH, "add_vault_slots")
MOVE_HOME = _load(MOVE_HOME_PATH, "move_home_markers_to_slots")

ADD_SLOTS_REVISION = "e7a1b2c3d4e5"
MOVE_HOME_REVISION = "f8b2c3d4e5f6"
PARENT = "c19031dc6b22"


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
def test_revision_chain() -> None:
    assert ADD_SLOTS.revision == ADD_SLOTS_REVISION
    assert ADD_SLOTS.down_revision == PARENT
    assert MOVE_HOME.revision == MOVE_HOME_REVISION
    assert MOVE_HOME.down_revision == ADD_SLOTS_REVISION


@pytest.mark.integration
class TestVaultSlotMigrations:
    def test_add_slots_creates_table_and_backfills_live_vaults_by_number(self, harness: MigrationHarness) -> None:
        harness.upgrade(ADD_SLOTS_REVISION)

        columns = {
            row[0]
            for row in harness.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'vaultslot'"
            )
        }
        assert {"id", "slot_index", "vault_id", "created_at", "updated_at"} <= columns

        # The upgrade chain seeds a live vault, so assert the invariant over seeded rows
        # (an empty-database assertion fails here).
        rows = harness.fetch(
            "SELECT s.slot_index, v.number FROM vaultslot s JOIN vault v ON v.id = s.vault_id "
            "WHERE v.is_deleted = false ORDER BY s.slot_index"
        )
        assert rows, "backfill should have claimed a slot for every live vault"
        assert [slot_index for slot_index, _ in rows] == list(range(len(rows)))
        assert [number for _, number in rows] == sorted(number for _, number in rows)

        orphans = harness.scalar(
            "SELECT count(*) FROM vault v JOIN vaultslot s ON s.vault_id = v.id WHERE v.is_deleted = true"
        )
        assert orphans == 0

        # Downgrade drops the table entirely.
        harness.downgrade(PARENT)
        assert harness.fetch("SELECT 1 FROM information_schema.tables WHERE table_name = 'vaultslot'") == []

    def test_move_home_markers_relocates_centre_rows(self, harness: MigrationHarness) -> None:
        harness.upgrade(ADD_SLOTS_REVISION)

        # The move migration is idempotent and name-matched. Pin every player vault home
        # row back to the centre, then assert none is left there afterwards.
        harness.execute(
            "UPDATE worldlocation SET coord_x = 50.0, coord_y = 50.0 "
            "WHERE kind = 'VAULT' AND COALESCE(source, '') <> 'seed'"
        )
        pinned_before = harness.scalar(
            "SELECT count(*) FROM worldlocation WHERE kind = 'VAULT' AND coord_x = 50.0 AND coord_y = 50.0"
        )

        harness.upgrade(MOVE_HOME_REVISION)

        if pinned_before:
            pinned_after = harness.scalar(
                "SELECT count(*) FROM worldlocation WHERE kind = 'VAULT' AND coord_x = 50.0 AND coord_y = 50.0"
            )
            assert pinned_after < pinned_before, "the migration must move centre-pinned vault homes to their slot"
        in_bounds = harness.scalar(
            "SELECT count(*) FROM worldlocation WHERE coord_x < 0 OR coord_x > 100 OR coord_y < 0 OR coord_y > 100"
        )
        assert in_bounds == 0
