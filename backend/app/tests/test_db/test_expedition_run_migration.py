import inspect

from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration("2026_09_25_0001-b80551876fa9_add_expedition_run.py", "add_expedition_run")


def test_revision_chain() -> None:
    assert MIGRATION.revision == "b80551876fa9"
    assert MIGRATION.down_revision == "f4e5d6c7b8a9"


def test_final_table_and_open_run_indexes() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert 'sa.Column("finished_at"' in source
    assert "cleared_at" not in source
    assert "uq_expeditionrun_open_exploration" in source
    assert "uq_expeditionrun_open_vault_site" in source
    assert "vault_id" in source
    assert "site_id" in source
    assert "ENTERED" in source
    assert "IN_ROOM" in source


def test_downgrade_drops_table_and_enum() -> None:
    source = inspect.getsource(MIGRATION.downgrade)
    assert 'drop_table("expeditionrun")' in source
    assert 'sa.Enum(name="expeditionrunstatus").drop' in source
