"""Regression coverage for the Room Rush state and notification enum migrations."""

import importlib.util
import inspect
from pathlib import Path

from app.models.room import Room

MIGRATIONS_DIR = Path(__file__).parents[2] / "alembic/versions"


def _load_migration(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, MIGRATIONS_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_migration(revision: str) -> Path:
    matches = sorted(MIGRATIONS_DIR.glob(f"*-{revision}_*.py"))
    assert len(matches) == 1, f"Expected one migration for {revision}, found {matches}"
    return matches[0]


ROOM_STATE = _load_migration(_find_migration("a1c3e5f7b9d2").name, "add_room_rush_state")
RUSH_NOTIFICATIONS = _load_migration(_find_migration("b2d4f6a8c0e1").name, "add_rush_notification_types")


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
