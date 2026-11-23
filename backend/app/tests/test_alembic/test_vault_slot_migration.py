from __future__ import annotations

import pytest

from app.tests.test_alembic._support import load_migration
from app.tests.test_alembic.test_data_migrations import MigrationHarness

pytest_plugins = ["app.tests.test_alembic.test_data_migrations"]

ADD_SLOTS = load_migration("2026_10_02_0001-e7a1b2c3d4e5_add_vault_slots.py", "add_vault_slots")
MOVE_HOME = load_migration("2026_10_02_0002-f8b2c3d4e5f6_move_home_markers_to_slots.py", "move_home_markers_to_slots")
ADD_SLOTS_REVISION = "e7a1b2c3d4e5"
MOVE_HOME_REVISION = "f8b2c3d4e5f6"
PARENT = "c19031dc6b22"


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
        # The upgrade chain seeds a live vault, so assert the invariant over seeded rows.
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
        harness.downgrade(PARENT)
        assert harness.fetch("SELECT 1 FROM information_schema.tables WHERE table_name = 'vaultslot'") == []

    def test_move_home_markers_relocates_centre_rows(self, harness: MigrationHarness) -> None:
        harness.upgrade(ADD_SLOTS_REVISION)
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
