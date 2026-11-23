import inspect

from app.models.room import Room
from app.tests.test_alembic._support import load_migration

ROOM_STATE = load_migration("2026_10_24_1102-a1c3e5f7b9d2_add_room_rush_state.py", "add_room_rush_state")
RUSH_NOTIFICATIONS = load_migration(
    "2026_10_24_1103-b2d4f6a8c0e1_add_rush_notification_types.py", "add_rush_notification_types"
)


def test_room_rush_revision_chain() -> None:
    assert ROOM_STATE.revision == "a1c3e5f7b9d2"
    assert ROOM_STATE.down_revision == "b4d8f2a6c0e1"
    assert RUSH_NOTIFICATIONS.revision == "b2d4f6a8c0e1"
    assert RUSH_NOTIFICATIONS.down_revision == ROOM_STATE.revision


def test_room_state_migration_adds_columns_without_backfill() -> None:
    source = inspect.getsource(ROOM_STATE.upgrade)
    assert '"rush_stacks"' in source
    assert 'server_default="0"' in source
    assert '"last_rush_at"' in source
    assert "nullable=True" in source
    assert "UPDATE" not in source


def test_room_state_downgrade_drops_both_columns() -> None:
    source = inspect.getsource(ROOM_STATE.downgrade)
    assert source.count("drop_column") == 2
    assert '"rush_stacks"' in source
    assert '"last_rush_at"' in source


def test_room_model_defaults_mean_never_rushed() -> None:
    assert Room.model_fields["rush_stacks"].default == 0
    assert Room.model_fields["last_rush_at"].default is None


def test_notification_enum_migration_and_noop_downgrade() -> None:
    upgrade = inspect.getsource(RUSH_NOTIFICATIONS.upgrade)
    assert "ADD VALUE IF NOT EXISTS 'RUSH_SUCCEEDED'" in upgrade
    assert "ADD VALUE IF NOT EXISTS 'RUSH_FAILED'" in upgrade
    assert "pass" in inspect.getsource(RUSH_NOTIFICATIONS.downgrade)
