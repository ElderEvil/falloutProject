"""Regression coverage for the hazard-team consolidation migration.

The earned fire/radiation rosters moved from the parallel ``hazard_team_member``
table onto the reusable ``team``/``team_member`` primitive. This test pins the
migration's revision chain, the three-way purpose check, and the member
backfill's status-to-slot mapping: living ``active`` members hold slots 1-3 in
seniority order, while ``reserve`` and fallen members hold no slot (NULL).
"""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_09_19_0003-c9d8e7f6a5b4_consolidate_hazard_teams_onto_team_roster.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("consolidate_hazard_teams", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_revision_chain() -> None:
    assert MIGRATION.down_revision == "b7c8d9e0f1a2"


def test_three_way_purpose_check_covers_all_purposes() -> None:
    sql = MIGRATION.THREE_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" in sql


def test_downgrade_restores_two_way_purpose_check() -> None:
    sql = MIGRATION.TWO_WAY_PURPOSE_CHECK
    assert "quest_id IS NOT NULL" in sql
    assert "incident_id IS NOT NULL" in sql
    assert "hazard_team IS NOT NULL" not in sql


def test_member_backfill_assigns_slots_to_living_active_only() -> None:
    sql = str(MIGRATION.MEMBER_BACKFILL_SQL)
    assert "ROW_NUMBER() OVER" in sql
    assert "status = 'active'" in sql
    assert "is_dead = FALSE" in sql
    assert "is_deleted = FALSE" in sql
    assert "slot_number" in sql


def test_member_backfill_copies_timestamps() -> None:
    sql = str(MIGRATION.MEMBER_BACKFILL_SQL)
    assert "htm.created_at" in sql
    assert "htm.updated_at" in sql


def test_team_backfill_groups_by_vault_and_hazard() -> None:
    sql = str(MIGRATION.TEAM_BACKFILL_SQL)
    assert "GROUP BY vault_id, team" in sql
    assert "hazard_team" in sql


def test_downgrade_restores_members_from_hazard_teams() -> None:
    sql = str(MIGRATION.MEMBER_RESTORE_SQL)
    assert "hazard_team IS NOT NULL" in sql
    assert "tm.created_at" in sql
    assert "tm.updated_at" in sql
