from app.tests.test_alembic._support import load_migration
from app.tests.test_db.test_enum_drift import PG_ENUM_LABELS_SNAPSHOT

MIGRATION = load_migration(
    "2026_08_23_0001-9f8e7d6c5b4a3_squash_arena_incident_combat.py", "squash_arena_incident_combat"
)

# Labels added to the persisted enums by migrations that shipped AFTER this squash.
# Every post-squash ADD VALUE migration must extend the matching set here, or this guard drifts.
ROOM_TYPE_LABELS_ADDED_AFTER_SQUASH: set[str] = {"ARENA", "RESPONSE"}
DWELLER_STATUS_LABELS_ADDED_AFTER_SQUASH: set[str] = {"FIGHTING"}


def test_upgrade_labels_match_enum_drift_snapshot() -> None:
    snapshot_room = PG_ENUM_LABELS_SNAPSHOT["roomtypeenum"]
    snapshot_status = PG_ENUM_LABELS_SNAPSHOT["dwellerstatusenum"]
    assert snapshot_room >= ROOM_TYPE_LABELS_ADDED_AFTER_SQUASH
    assert snapshot_status >= DWELLER_STATUS_LABELS_ADDED_AFTER_SQUASH


def test_downgrade_labels_are_snapshot_minus_branch_labels() -> None:
    snapshot_room = PG_ENUM_LABELS_SNAPSHOT["roomtypeenum"]
    snapshot_status = PG_ENUM_LABELS_SNAPSHOT["dwellerstatusenum"]
    assert set(MIGRATION.ROOM_TYPE_LABELS) == snapshot_room - ROOM_TYPE_LABELS_ADDED_AFTER_SQUASH
    assert set(MIGRATION.DWELLER_STATUS_LABELS) == snapshot_status - DWELLER_STATUS_LABELS_ADDED_AFTER_SQUASH


def test_downgrade_recreates_enums_without_branch_labels() -> None:
    room_enum = ", ".join(repr(label) for label in MIGRATION.ROOM_TYPE_LABELS)
    status_enum = ", ".join(repr(label) for label in MIGRATION.DWELLER_STATUS_LABELS)
    assert "ARENA" not in room_enum
    assert "FIGHTING" not in status_enum
    assert "MISC" in room_enum
    assert "WORKING" in status_enum
