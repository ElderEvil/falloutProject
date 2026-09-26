"""Regression coverage for the exploration party-team migration (issue 772)."""

import importlib.util
import inspect
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic/versions/2026_09_26_0004-b5a4c3d2e1f0_add_exploration_party_team.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("add_exploration_party_team", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.revision == "b5a4c3d2e1f0"
    assert MIGRATION.down_revision == "a3b4c5d6e7f8"


def test_upgrade_adds_team_exploration_column_and_constraints() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert 'sa.Column("exploration_id", sa.Uuid(), nullable=True)' in source
    assert "uq_team_vault_exploration" in source
    assert "ix_team_exploration_id" in source


def test_upgrade_adds_exploration_team_fk() -> None:
    source = inspect.getsource(MIGRATION.upgrade)
    assert 'sa.Column("team_id", sa.Uuid(), nullable=True)' in source
    assert "fk_exploration_team_id" in source
    assert "SET NULL" in source


def test_four_way_purpose_check_covers_all_purposes() -> None:
    sql = MIGRATION.FOUR_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" in sql
    assert "exploration_id IS NOT NULL" in sql


def test_downgrade_restores_three_way_purpose_check() -> None:
    sql = MIGRATION.THREE_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" in sql
    assert "exploration_id IS NOT NULL" not in sql


def test_downgrade_deletes_party_rows_before_restoring_check() -> None:
    source = inspect.getsource(MIGRATION.downgrade)
    assert "DELETE FROM team WHERE exploration_id IS NOT NULL" in source
    assert "uq_team_vault_exploration" in source
    assert 'op.drop_column("exploration", "team_id")' in source
