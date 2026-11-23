from app.tests.test_alembic._support import load_migration

MIGRATION = load_migration("2026_09_26_0004-b5a4c3d2e1f0_add_exploration_party_team.py", "add_exploration_party_team")


def test_revision_chain() -> None:
    assert MIGRATION.revision == "b5a4c3d2e1f0"
    assert MIGRATION.down_revision == "a3b4c5d6e7f8"


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
