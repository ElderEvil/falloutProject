"""Regression coverage for the squashed arena + incident migration.

Verifies the migration's enum label sets stay consistent with the
PG_ENUM_LABELS_SNAPSHOT in test_enum_drift.py: the upgrade adds ARENA and
FIGHTING (matching the live DB), and the downgrade rebuilds both enum types
with exactly the pre-branch labels so a downgrade never drops a label that
still exists in the snapshot.
"""

import importlib.util
from pathlib import Path

from app.tests.test_db.test_enum_drift import PG_ENUM_LABELS_SNAPSHOT

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_08_23_0001-9f8e7d6c5b4a3_squash_arena_incident_combat.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("squash_arena_incident_combat", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_upgrade_labels_match_enum_drift_snapshot() -> None:
    snapshot_room = PG_ENUM_LABELS_SNAPSHOT["roomtypeenum"]
    snapshot_status = PG_ENUM_LABELS_SNAPSHOT["dwellerstatusenum"]

    assert "ARENA" in snapshot_room
    assert "FIGHTING" in snapshot_status


def test_downgrade_labels_are_snapshot_minus_branch_labels() -> None:
    snapshot_room = PG_ENUM_LABELS_SNAPSHOT["roomtypeenum"]
    snapshot_status = PG_ENUM_LABELS_SNAPSHOT["dwellerstatusenum"]

    assert set(MIGRATION.ROOM_TYPE_LABELS) == snapshot_room - {"ARENA"}
    assert set(MIGRATION.DWELLER_STATUS_LABELS) == snapshot_status - {"FIGHTING"}


def test_downgrade_recreates_enums_without_branch_labels() -> None:
    room_enum = ", ".join(repr(label) for label in MIGRATION.ROOM_TYPE_LABELS)
    status_enum = ", ".join(repr(label) for label in MIGRATION.DWELLER_STATUS_LABELS)

    assert "ARENA" not in room_enum
    assert "FIGHTING" not in status_enum
    assert "MISC" in room_enum
    assert "WORKING" in status_enum
