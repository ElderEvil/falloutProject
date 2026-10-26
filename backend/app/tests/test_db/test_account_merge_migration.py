"""Migration fragment coverage for the account_merge audit table."""

import importlib.util
import inspect
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parents[2] / "alembic/versions"
MIGRATION_PATH = next(MIGRATIONS_DIR.glob("*-a9f3c2d1e8b7_add_account_merge.py"), None)
assert MIGRATION_PATH is not None, "account_merge migration not found"
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_account_merge", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)

REQUIRED_COLUMNS = (
    "id",
    "source_user_id",
    "target_user_id",
    "actor_user_id",
    "source_username",
    "target_username",
    "source_email",
    "target_email",
    "reason",
    "moved_counts",
    "created_at",
)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "a9f3c2d1e8b7"
    assert MIGRATION.down_revision == "e2b4c6d8f012"


def test_upgrade_creates_account_merge_table_with_required_columns() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert 'op.create_table(\n        "account_merge"' in source
    for column in REQUIRED_COLUMNS:
        assert f'"{column}"' in source, f"missing column {column}"


def test_moved_counts_uses_portable_json() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert "sa.JSON()" in source
    assert "JSONB" not in source


def test_source_user_id_is_uniquely_constrained() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert 'sa.UniqueConstraint("source_user_id", name="uq_account_merge_source_user_id")' in source


def test_user_foreign_keys_restrict_deletion() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    for column in ("source_user_id", "target_user_id", "actor_user_id"):
        assert f'sa.ForeignKeyConstraint(["{column}"], ["user.id"], ondelete="RESTRICT")' in source


def test_downgrade_drops_indexes_and_table() -> None:
    source = inspect.getsource(MIGRATION.downgrade)
    for index in (
        "ix_account_merge_id",
        "ix_account_merge_target_user_id",
        "ix_account_merge_actor_user_id",
        "ix_account_merge_created_at",
    ):
        assert index in source
    assert source.count("op.drop_index") == 4
    assert 'op.drop_table("account_merge")' in source
