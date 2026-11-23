import inspect

from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration("a9f3c2d1e8b7", "add_account_merge")

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
